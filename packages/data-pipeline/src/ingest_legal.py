#!/usr/bin/env python3
"""
Pipeline d'ingestion juridique pour le système RAG
Sources : Légifrance (Code civil successions) + BOFIP (barèmes mutations)

Workflow :
1. LegiFranceIngester : récupère les articles 720-892 du Code civil
2. BOFIPIngester : scrape les pages barèmes mutations à titre gratuit
3. EmbeddingPipeline : chunking (512 tokens, overlap 50) + embeddings Ollama

Usage :
    python ingest_legal.py --source legifrance  # Code civil uniquement
    python ingest_legal.py --source bofip       # BOFIP uniquement
    python ingest_legal.py --source all         # Sources complètes
"""

import asyncio
import hashlib
import json
import os
import re
import argparse
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin

import aiohttp
import asyncpg
from bs4 import BeautifulSoup
import tiktoken


@dataclass
class LegalChunk:
    """Représente un chunk de contenu juridique"""
    source: str  # ex: "Code civil art.734"
    source_type: str  # 'loi' | 'jurisprudence' | 'bofip' | 'acte_type'
    content: str  # texte du chunk (512 tokens max)
    metadata: dict  # informations additionnelles

    @property
    def content_hash(self) -> str:
        """Hash SHA256 pour déduplication"""
        return hashlib.sha256(self.content.encode()).hexdigest()


class LegiFranceIngester:
    """
    Ingestion des articles du Code civil via l'API Légifrance PISTE
    Cible : articles 720-892 (successions et libéralités)
    """

    def __init__(self, client_id: str = None, client_secret: str = None):
        self.client_id = client_id or os.getenv("LEGIFRANCE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("LEGIFRANCE_CLIENT_SECRET")
        self.base_url = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
        self.token = None

    async def get_access_token(self, session: aiohttp.ClientSession) -> str:
        """Obtient un token OAuth2 pour l'API PISTE"""
        if not self.client_id or not self.client_secret:
            raise ValueError("LEGIFRANCE_CLIENT_ID et LEGIFRANCE_CLIENT_SECRET requis")

        token_url = "https://api.piste.gouv.fr/oauth/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "openid"
        }

        async with session.post(token_url, data=data) as resp:
            resp.raise_for_status()
            token_data = await resp.json()
            return token_data["access_token"]

    async def fetch_article(self, session: aiohttp.ClientSession, article_num: int) -> Optional[LegalChunk]:
        """
        Récupère un article spécifique du Code civil

        Note: Cette méthode est simplifiée pour le prototype.
        En production, il faudrait:
        1. Mapper article_num vers l'ID Légifrance exact
        2. Gérer les articles bis, ter, etc.
        3. Traiter les modifications temporelles
        """
        if not self.token:
            self.token = await self.get_access_token(session)

        headers = {"Authorization": f"Bearer {self.token}"}

        # Exemple d'endpoint (à adapter selon l'API réelle)
        url = f"{self.base_url}/consult/getArticle"
        payload = {
            "id": f"LEGIARTI0000{article_num:08d}",  # Format ID Légifrance simplifié
            "textId": "LEGITEXT000006070721"  # Code civil
        }

        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 404:
                    return None  # Article non trouvé
                resp.raise_for_status()
                data = await resp.json()

                # Extraction du contenu (structure API à vérifier)
                article_data = data.get("article", {})
                content = article_data.get("texte", "")

                if not content:
                    return None

                return LegalChunk(
                    source=f"Code civil art.{article_num}",
                    source_type="loi",
                    content=content.strip(),
                    metadata={
                        "article": article_num,
                        "code": "civil",
                        "url": f"https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI0000{article_num:08d}",
                        "date_version": datetime.now().isoformat()
                    }
                )
        except Exception as e:
            print(f"Erreur récupération article {article_num}: {e}")
            return None

    async def ingest_successions_articles(self) -> List[LegalChunk]:
        """Ingère les articles 720-892 du Code civil (successions)"""
        chunks = []

        async with aiohttp.ClientSession() as session:
            for article_num in range(720, 893):  # Articles 720-892
                if article_num % 20 == 0:
                    print(f"Ingestion article {article_num}...")

                chunk = await self.fetch_article(session, article_num)
                if chunk:
                    chunks.append(chunk)

                # Rate limiting API
                await asyncio.sleep(0.1)

        print(f"Légifrance : {len(chunks)} articles ingérés")
        return chunks


class BOFIPIngester:
    """
    Scraping structuré des pages BOFIP
    Cible : barèmes mutations à titre gratuit (successions/donations)
    """

    def __init__(self):
        self.base_url = "https://bofip.impots.gouv.fr"
        self.target_pages = [
            "1-PGP",    # Page générale
            "3169-PGP", # Droits de succession
            "3170-PGP", # Droits de donation
            "3171-PGP"  # Abattements
        ]

    async def scrape_bofip_page(self, session: aiohttp.ClientSession, page_id: str) -> List[LegalChunk]:
        """Scrape une page BOFIP spécifique"""
        url = f"{self.base_url}/bofip/{page_id}.html"
        chunks = []

        try:
            async with session.get(url) as resp:
                resp.raise_for_status()
                html = await resp.text()

            soup = BeautifulSoup(html, 'html.parser')

            # Extraction du titre principal
            title = soup.find('h1')
            title_text = title.get_text().strip() if title else f"BOFIP {page_id}"

            # Extraction des sections de contenu
            content_divs = soup.find_all(['div'], class_=['art-content', 'bofip-content'])

            for i, div in enumerate(content_divs):
                content = div.get_text(separator=' ').strip()

                # Filtrer le contenu trop court
                if len(content) < 100:
                    continue

                chunks.append(LegalChunk(
                    source=f"BOFIP {page_id} section {i+1}",
                    source_type="bofip",
                    content=content,
                    metadata={
                        "page_id": page_id,
                        "title": title_text,
                        "url": url,
                        "section": i+1,
                        "date_scrape": datetime.now().isoformat()
                    }
                ))

        except Exception as e:
            print(f"Erreur scraping BOFIP {page_id}: {e}")

        return chunks

    async def ingest_bofip_mutations(self) -> List[LegalChunk]:
        """Ingère toutes les pages BOFIP sur les mutations à titre gratuit"""
        all_chunks = []

        async with aiohttp.ClientSession() as session:
            for page_id in self.target_pages:
                print(f"Scraping BOFIP {page_id}...")
                chunks = await self.scrape_bofip_page(session, page_id)
                all_chunks.extend(chunks)

                # Rate limiting
                await asyncio.sleep(1)

        print(f"BOFIP : {len(all_chunks)} chunks ingérés")
        return all_chunks


class EmbeddingPipeline:
    """
    Pipeline de chunking et génération d'embeddings
    Utilise Ollama avec nomic-embed-text (768 dimensions)
    """

    def __init__(self, ollama_url: str = None):
        self.ollama_url = ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.embedding_model = "nomic-embed-text"
        self.tokenizer = tiktoken.get_encoding("cl100k_base")  # Approximation GPT
        self.max_tokens = 512
        self.overlap_tokens = 50

    def chunk_content(self, content: str) -> List[str]:
        """
        Découpe le contenu en chunks de 512 tokens max avec overlap de 50 tokens
        Respecte les frontières de phrase
        """
        # Tokenisation
        tokens = self.tokenizer.encode(content)

        if len(tokens) <= self.max_tokens:
            return [content]  # Pas besoin de découper

        chunks = []
        start_idx = 0

        while start_idx < len(tokens):
            end_idx = min(start_idx + self.max_tokens, len(tokens))

            # Décodage du chunk
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_text = self.tokenizer.decode(chunk_tokens)

            # Découpage intelligent aux limites de phrase
            if end_idx < len(tokens):  # Pas le dernier chunk
                # Chercher la dernière phrase complète
                sentences = re.split(r'[.!?]', chunk_text)
                if len(sentences) > 1:
                    # Garder toutes les phrases sauf la dernière incomplète
                    complete_text = '.'.join(sentences[:-1]) + '.'
                    chunk_text = complete_text.strip()

            chunks.append(chunk_text)

            # Calculer le prochain start avec overlap
            if end_idx >= len(tokens):
                break
            start_idx = end_idx - self.overlap_tokens

        return chunks

    async def generate_embedding(self, session: aiohttp.ClientSession, text: str) -> List[float]:
        """Génère un embedding via Ollama"""
        url = f"{self.ollama_url}/api/embeddings"
        payload = {
            "model": self.embedding_model,
            "prompt": text
        }

        async with session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["embedding"]

    async def process_chunks(self, legal_chunks: List[LegalChunk]) -> List[Tuple[LegalChunk, List[float]]]:
        """
        Traite une liste de chunks : découpage + génération embeddings
        Retourne (chunk, embedding) pairs
        """
        processed_chunks = []

        async with aiohttp.ClientSession() as session:
            for legal_chunk in legal_chunks:
                # Découpage en sous-chunks si nécessaire
                sub_chunks = self.chunk_content(legal_chunk.content)

                for i, sub_content in enumerate(sub_chunks):
                    # Créer un nouveau chunk pour chaque sous-partie
                    sub_chunk = LegalChunk(
                        source=f"{legal_chunk.source}" + (f" partie {i+1}" if len(sub_chunks) > 1 else ""),
                        source_type=legal_chunk.source_type,
                        content=sub_content,
                        metadata={
                            **legal_chunk.metadata,
                            "chunk_index": i,
                            "total_chunks": len(sub_chunks)
                        }
                    )

                    # Générer l'embedding
                    try:
                        embedding = await self.generate_embedding(session, sub_content)
                        processed_chunks.append((sub_chunk, embedding))

                        if len(processed_chunks) % 10 == 0:
                            print(f"Embeddings générés : {len(processed_chunks)}")

                    except Exception as e:
                        print(f"Erreur embedding pour '{legal_chunk.source}': {e}")
                        continue

                    # Rate limiting
                    await asyncio.sleep(0.1)

        print(f"Pipeline : {len(processed_chunks)} chunks avec embeddings")
        return processed_chunks


class LegalIngestionService:
    """Service principal d'ingestion juridique"""

    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self.legifrance = LegiFranceIngester()
        self.bofip = BOFIPIngester()
        self.embedding_pipeline = EmbeddingPipeline()

    async def init_database(self) -> asyncpg.Connection:
        """Initialise la connexion DB et vérifie le schéma"""
        conn = await asyncpg.connect(self.db_url)

        # Vérifier que pgvector est disponible
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # Créer la table knowledge_chunks si elle n'existe pas
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source VARCHAR(255) NOT NULL,
                source_type VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                content_hash VARCHAR(64) UNIQUE NOT NULL,
                embedding vector(768) NOT NULL,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Créer l'index IVFFlat pour la recherche vectorielle
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding
            ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)

        # Index pour les requêtes par type
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_source_type
            ON knowledge_chunks (source_type)
        """)

        return conn

    async def store_chunks(self, conn: asyncpg.Connection,
                          chunks_with_embeddings: List[Tuple[LegalChunk, List[float]]]):
        """Stocke les chunks en base avec déduplication"""
        inserted_count = 0

        for chunk, embedding in chunks_with_embeddings:
            try:
                await conn.execute("""
                    INSERT INTO knowledge_chunks
                    (source, source_type, content, content_hash, embedding, metadata)
                    VALUES ($1, $2, $3, $4, $5::vector, $6)
                    ON CONFLICT (content_hash) DO NOTHING
                """,
                chunk.source,
                chunk.source_type,
                chunk.content,
                chunk.content_hash,
                json.dumps(embedding),
                json.dumps(chunk.metadata))

                inserted_count += 1

            except Exception as e:
                print(f"Erreur insertion chunk '{chunk.source}': {e}")
                continue

        print(f"Base de données : {inserted_count} chunks insérés")
        return inserted_count

    async def ingest_source(self, source: str) -> Dict[str, int]:
        """
        Ingère une source spécifique
        source: 'legifrance' | 'bofip' | 'all'
        """
        conn = await self.init_database()
        stats = {"legifrance": 0, "bofip": 0}

        try:
            if source in ['legifrance', 'all']:
                print("=== Ingestion Légifrance ===")
                legifrance_chunks = await self.legifrance.ingest_successions_articles()
                legifrance_processed = await self.embedding_pipeline.process_chunks(legifrance_chunks)
                stats["legifrance"] = await self.store_chunks(conn, legifrance_processed)

            if source in ['bofip', 'all']:
                print("=== Ingestion BOFIP ===")
                bofip_chunks = await self.bofip.ingest_bofip_mutations()
                bofip_processed = await self.embedding_pipeline.process_chunks(bofip_chunks)
                stats["bofip"] = await self.store_chunks(conn, bofip_processed)

            # Log du pipeline_run
            await conn.execute("""
                INSERT INTO pipeline_runs (source, statut, nb_lignes, started_at, finished_at)
                VALUES ($1, $2, $3, NOW(), NOW())
            """, f"LEGAL_{source.upper()}", "terminé", stats["legifrance"] + stats["bofip"])

        finally:
            await conn.close()

        return stats


async def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description="Pipeline d'ingestion juridique RAG")
    parser.add_argument("--source", choices=["legifrance", "bofip", "all"],
                       default="all", help="Source à ingérer")

    args = parser.parse_args()

    print(f"🏛️ Démarrage ingestion juridique - source: {args.source}")

    service = LegalIngestionService()
    stats = await service.ingest_source(args.source)

    print(f"✅ Ingestion terminée :")
    print(f"   - Légifrance : {stats['legifrance']} chunks")
    print(f"   - BOFIP : {stats['bofip']} chunks")
    print(f"   - Total : {sum(stats.values())} chunks")


if __name__ == "__main__":
    asyncio.run(main())