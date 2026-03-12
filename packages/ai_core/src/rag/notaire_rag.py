#!/usr/bin/env python3
"""
Service RAG (Retrieval-Augmented Generation) pour le domaine notarial

Architecture :
1. NotaireRAG.search() : recherche vectorielle dans knowledge_chunks
2. NotaireRAG.answer() : génération de réponse citant les sources

Usage :
    rag = NotaireRAG()
    chunks = await rag.search("Comment calculer les droits de succession ?", source_type="loi")
    answer = await rag.answer("Comment calculer les droits de succession ?", chunks)
"""

import json
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import asyncpg
import aiohttp

from ..providers import get_ai_provider, OllamaProvider


@dataclass
class ChunkResult:
    """Représente un chunk de connaissance récupéré (compatible tests TDD)"""
    id: str
    source: str
    source_type: str
    content: str
    metadata: Dict
    similarity: float

    def to_dict(self) -> Dict:
        """Conversion en dictionnaire pour JSON"""
        return {
            "id": self.id,
            "source": self.source,
            "source_type": self.source_type,
            "content": self.content,
            "metadata": self.metadata,
            "similarity": self.similarity
        }


# Alias pour compatibilité
KnowledgeChunk = ChunkResult


@dataclass
class RAGResponse:
    """Réponse structurée du système RAG (compatible tests TDD)"""
    reponse: str
    sources_citees: List[str]
    confiance: float
    avertissements: List[str] = None

    def __post_init__(self):
        if self.avertissements is None:
            self.avertissements = []

    def to_dict(self) -> Dict:
        """Conversion en dictionnaire pour API"""
        return {
            "reponse": self.reponse,
            "sources_citees": self.sources_citees,
            "confiance": self.confiance,
            "avertissements": self.avertissements
        }


class NotaireRAG:
    """
    Système RAG spécialisé pour le domaine notarial français

    Fonctionnalités :
    - Recherche sémantique dans les textes juridiques
    - Génération de réponses citant les sources légales
    - Filtrage par type de source (loi, bofip, jurisprudence)
    - Seuil de similarité configurable pour la pertinence
    """

    def __init__(self,
                 db_url: str = None,
                 similarity_threshold: float = 0.75,
                 embedding_model: str = "nomic-embed-text",
                 ollama_url: str = None):
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self.similarity_threshold = similarity_threshold
        self.embedding_model = embedding_model

        # Connexion DB - peut être mockée pour les tests
        self._db_conn = None

        # Pour les embeddings, on utilise toujours Ollama
        # même si le provider principal est Anthropic
        self.embedding_provider = OllamaProvider(
            model=embedding_model,
            base_url=ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )

        # Provider principal pour la génération de réponses
        self.llm_provider = get_ai_provider()

    async def _get_db_connection(self) -> asyncpg.Connection:
        """Obtient une connexion à la base de données"""
        # Permet le mock pour les tests
        if self._db_conn is not None:
            return self._db_conn
        return await asyncpg.connect(self.db_url)

    async def embed_query(self, query: str) -> Tuple[List[float], float]:
        """
        Génère l'embedding d'une requête
        Retourne (embedding, temps_ms)
        """
        import time
        start_time = time.time()

        # Normaliser la requête
        normalized_query = query.strip().lower()

        # Générer l'embedding
        embedding = await self.embedding_provider.embed(normalized_query)

        embedding_time = (time.time() - start_time) * 1000
        return embedding, embedding_time

    async def search(self,
                    query: str,
                    source_type: Optional[str] = None,
                    k: int = 5,
                    threshold: float = None) -> List[ChunkResult]:
        """
        Recherche vectorielle dans la base de connaissances

        Args:
            query: Question ou requête en langage naturel
            source_type: Filtrer par type ('loi', 'bofip', 'jurisprudence', 'acte_type')
            k: Nombre maximum de résultats
            threshold: Seuil de similarité minimum (défaut: self.similarity_threshold)

        Returns:
            Liste des chunks pertinents
        """
        # Générer l'embedding de la requête
        query_embedding, _ = await self.embed_query(query)

        # Construire la requête SQL
        similarity_threshold = threshold or self.similarity_threshold

        base_query = """
            SELECT id, source, source_type, content, metadata,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM knowledge_chunks
            WHERE 1 - (embedding <=> $1::vector) > $2
        """

        params = [json.dumps(query_embedding), similarity_threshold]

        if source_type:
            base_query += " AND source_type = $3"
            params.append(source_type)

        base_query += """
            ORDER BY embedding <=> $1::vector
            LIMIT ${}
        """.format(len(params) + 1)

        params.append(k)

        # Exécuter la requête
        conn = await self._get_db_connection()
        try:
            rows = await conn.fetch(base_query, *params)
        finally:
            await conn.close()

        # Convertir en objets ChunkResult
        chunks = [
            ChunkResult(
                id=str(row['id']),
                source=row['source'],
                source_type=row['source_type'],
                content=row['content'],
                metadata=row['metadata'] or {},
                similarity=float(row['similarity'])
            )
            for row in rows
        ]

        return chunks

    def _build_rag_prompt(self, question: str, chunks: List[ChunkResult], context_dossier: str = None) -> str:
        """
        Construit le prompt RAG avec le contexte juridique

        Format :
        - Rôle de notaire expert
        - Sources légales comme contexte
        - Question spécifique
        - Consignes de citation
        """
        context_parts = []

        for chunk in chunks:
            context_parts.append(f"""
📚 Source : {chunk.source} (similarité: {chunk.similarity:.2f})
{chunk.content}
""")

        context = "\n".join(context_parts)

        # Ajouter contexte dossier si fourni
        dossier_info = ""
        if context_dossier:
            dossier_info = f"""
## Contexte du dossier :
{context_dossier}
"""

        prompt = f"""Tu es un notaire expert en droit français. Tu dois répondre à la question ci-dessous en te basant EXCLUSIVEMENT sur les sources légales fournies.

## Sources légales disponibles :
{context}
{dossier_info}
## Question du client :
{question}

## Instructions de réponse :
1. Réponds de manière claire et précise en français
2. Cite OBLIGATOIREMENT tes sources (ex: "Selon l'article 734 du Code civil...")
3. Si les sources ne permettent pas de répondre complètement, indique-le explicitement
4. Structure ta réponse avec des paragraphes distincts
5. Utilise un ton professionnel mais accessible
6. N'invente aucune information non présente dans les sources

## Réponse :"""

        return prompt

    async def answer(self,
                    question: str,
                    chunks: List[ChunkResult],
                    context_dossier: str = None) -> RAGResponse:
        """
        Génère une réponse à partir des chunks récupérés

        Args:
            question: Question originale
            chunks: Chunks de connaissance pertinents
            context_dossier: Contexte optionnel du dossier client

        Returns:
            RAGResponse avec réponse structurée
        """
        if not chunks:
            return RAGResponse(
                reponse="Le contexte fourni est insuffisant pour répondre précisément à cette question. Pouvez-vous reformuler ou être plus spécifique ?",
                sources_citees=[],
                confiance=0.0,
                avertissements=["Aucun contexte pertinent trouvé"]
            )

        # Construire le prompt RAG
        prompt = self._build_rag_prompt(question, chunks, context_dossier)

        # Générer la réponse
        try:
            # Conversion pour l'API du provider
            messages = [{"role": "user", "content": prompt}]
            system_prompt = "Tu es un expert en droit notarial français. Réponds de manière précise en citant tes sources."

            response = await self.llm_provider.complete(
                messages,
                system_prompt=system_prompt,
                temperature=0.3
            )

            answer_text = response.content if hasattr(response, 'content') else str(response)

            # Extraire les sources citées de la réponse
            sources_citees = []
            for chunk in chunks:
                if chunk.source.lower() in answer_text.lower():
                    sources_citees.append(chunk.source)

            # Calculer confiance basée sur les similarités
            confiance = self._calculate_confidence(chunks)

            # Avertissements si confiance faible
            avertissements = []
            if confiance < 0.7:
                avertissements.append("Confiance faible - vérifiez auprès d'un expert")

            return RAGResponse(
                reponse=answer_text.strip(),
                sources_citees=sources_citees,
                confiance=confiance,
                avertissements=avertissements
            )

        except Exception as e:
            error_msg = f"Erreur lors de la génération de la réponse : {str(e)}"
            return RAGResponse(
                reponse=error_msg,
                sources_citees=[],
                confiance=0.0,
                avertissements=["Erreur technique lors de la génération"]
            )

    def _calculate_confidence(self, chunks: List[ChunkResult]) -> float:
        """
        Calcule un score de confiance basé sur les similarités

        Logique :
        - Moyenne des similarités pondérée
        - Bonus si plusieurs sources convergent
        - Malus si peu de chunks trouvés
        """
        if not chunks:
            return 0.0

        # Moyenne pondérée des similarités (plus de poids aux premiers résultats)
        weighted_sim = 0.0
        weight_sum = 0.0

        for i, chunk in enumerate(chunks):
            weight = 1.0 / (i + 1)  # Poids décroissant
            weighted_sim += chunk.similarity * weight
            weight_sum += weight

        base_confidence = weighted_sim / weight_sum

        # Bonus diversité de sources
        source_types = set(chunk.source_type for chunk in chunks)
        diversity_bonus = min(len(source_types) * 0.1, 0.3)

        # Malus si peu de résultats
        quantity_factor = min(len(chunks) / 3.0, 1.0)

        final_confidence = min((base_confidence + diversity_bonus) * quantity_factor, 1.0)
        return round(final_confidence, 2)

    async def question_complete(self,
                               question: str,
                               source_type: Optional[str] = None,
                               k: int = 5,
                               context_dossier: str = None) -> RAGResponse:
        """
        Pipeline RAG complet : recherche + génération (interface TDD)

        Args:
            question: Question en langage naturel
            source_type: Filtrer par type de source
            k: Nombre de chunks à récupérer
            context_dossier: Contexte du dossier client

        Returns:
            RAGResponse avec réponse et sources
        """
        # Étape 1 : Recherche vectorielle
        chunks = await self.search(question, source_type, k)

        # Étape 2 : Génération de la réponse
        return await self.answer(question, chunks, context_dossier)

    async def query(self,
                   question: str,
                   source_type: Optional[str] = None,
                   k: int = 5,
                   context_dossier: str = None) -> RAGResponse:
        """
        Pipeline RAG complet : recherche + génération (legacy)

        Args:
            question: Question en langage naturel
            source_type: Filtrer par type de source
            k: Nombre de chunks à récupérer
            context_dossier: Contexte du dossier

        Returns:
            RAGResponse avec réponse et sources
        """
        # Déléguer à question_complete pour compatibilité
        return await self.question_complete(question, source_type, k, context_dossier)

    async def get_stats(self) -> Dict[str, int]:
        """Statistiques de la base de connaissances"""
        conn = await self._get_db_connection()
        try:
            # Total des chunks
            total_row = await conn.fetchrow("SELECT COUNT(*) as total FROM knowledge_chunks")
            total_chunks = total_row['total']

            # Répartition par type de source
            type_rows = await conn.fetch("""
                SELECT source_type, COUNT(*) as count
                FROM knowledge_chunks
                GROUP BY source_type
                ORDER BY count DESC
            """)

            by_type = {row['source_type']: row['count'] for row in type_rows}

            return {
                "total_chunks": total_chunks,
                "by_source_type": by_type
            }
        finally:
            await conn.close()


class NotaireRAGService:
    """Service singleton pour l'accès global au RAG"""

    _instance: Optional[NotaireRAG] = None

    @classmethod
    def get_instance(cls) -> NotaireRAG:
        """Retourne l'instance singleton du RAG"""
        if cls._instance is None:
            cls._instance = NotaireRAG()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset l'instance (utile pour les tests)"""
        cls._instance = None


# Factory function pour les imports externes
def get_notaire_rag() -> NotaireRAG:
    """Factory function pour obtenir l'instance RAG"""
    return NotaireRAGService.get_instance()