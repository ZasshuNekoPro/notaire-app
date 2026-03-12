#!/usr/bin/env python3
"""
Tests TDD pour le système RAG notarial.
Vérifie la recherche vectorielle et la génération de réponses juridiques.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from uuid import UUID, uuid4
from typing import List, Dict, Any
import json

# Mock des dépendances potentiellement indisponibles
@pytest.fixture
def mock_embedding_provider():
    """Mock du provider d'embeddings."""
    provider = Mock()
    provider.embed = AsyncMock(return_value=[0.1] * 768)  # Embedding 768D
    return provider

@pytest.fixture
def mock_ai_provider():
    """Mock du provider IA principal."""
    provider = Mock()
    provider.complete = AsyncMock()
    return provider

@pytest.fixture
def mock_db_connection():
    """Mock de connexion PostgreSQL."""
    conn = Mock()
    conn.fetch = AsyncMock()
    return conn

@pytest.fixture
def sample_chunks():
    """Chunks d'exemple pour les tests."""
    return [
        {
            'id': str(uuid4()),
            'source': 'Code civil art.734',
            'source_type': 'loi',
            'content': 'Les enfants ou leurs descendants succèdent à leurs père et mère, aïeuls, aïeules ou autres ascendants, sans distinction de sexe ni de primogéniture, et encore qu\'ils soient issus de différents mariages.',
            'similarity': 0.85,
            'metadata': {'article': 734, 'code': 'civil'}
        },
        {
            'id': str(uuid4()),
            'source': 'Code civil art.720',
            'source_type': 'loi',
            'content': 'Les successions s\'ouvrent par la mort, au dernier domicile du défunt.',
            'similarity': 0.78,
            'metadata': {'article': 720, 'code': 'civil'}
        },
        {
            'id': str(uuid4()),
            'source': 'BOFIP-ENR-DMTG-20-30',
            'source_type': 'bofip',
            'content': 'L\'abattement applicable aux donations et legs consentis aux enfants est fixé à 100 000 euros par enfant et par parent donateur.',
            'similarity': 0.82,
            'metadata': {'bofip_ref': 'ENR-DMTG-20-30'}
        }
    ]


class TestNotaireRAGSearch:
    """Tests de la méthode search()."""

    @pytest.mark.asyncio
    async def test_search_returns_relevant_chunks(self, mock_embedding_provider, mock_db_connection, sample_chunks):
        """Test que search() retourne des chunks pertinents pour 'succession enfant'."""
        from packages.ai_core.src.rag.notaire_rag import NotaireRAG

        # Mock du fetch PostgreSQL
        mock_db_connection.fetch.return_value = [
            Mock(
                id=chunk['id'],
                source=chunk['source'],
                source_type=chunk['source_type'],
                content=chunk['content'],
                similarity=chunk['similarity'],
                metadata=json.dumps(chunk['metadata'])
            )
            for chunk in sample_chunks
        ]

        # Mock des providers
        with patch('packages.ai_core.src.rag.notaire_rag.OllamaProvider') as mock_ollama:
            mock_ollama.return_value = mock_embedding_provider

            rag = NotaireRAG()
            rag._db_conn = mock_db_connection

            results = await rag.search("succession enfant")

            # Vérifications
            assert len(results) > 0
            assert any(chunk.source_type == 'loi' for chunk in results)
            assert any('enfant' in chunk.content.lower() or 'succession' in chunk.content.lower() for chunk in results)

            # Vérifier que embed() a été appelé
            mock_embedding_provider.embed.assert_called_once_with("succession enfant")

            # Vérifier que la requête SQL a été appelée
            mock_db_connection.fetch.assert_called_once()
            sql_call = mock_db_connection.fetch.call_args[0][0]
            assert "ORDER BY embedding <=> $1::vector" in sql_call

    @pytest.mark.asyncio
    async def test_similarity_threshold(self, mock_embedding_provider, mock_db_connection):
        """Test que seuls les résultats avec score >= 0.75 sont retournés."""
        from packages.ai_core.src.rag.notaire_rag import NotaireRAG

        # Chunks avec scores variés
        chunks_mixed_scores = [
            Mock(
                id=str(uuid4()),
                source='Code civil art.720',
                source_type='loi',
                content='Succession content',
                similarity=0.85,  # > 0.75 ✅
                metadata='{}'
            ),
            Mock(
                id=str(uuid4()),
                source='Code civil art.721',
                source_type='loi',
                content='Other content',
                similarity=0.65,  # < 0.75 ❌
                metadata='{}'
            ),
            Mock(
                id=str(uuid4()),
                source='Code civil art.722',
                source_type='loi',
                content='Relevant content',
                similarity=0.80,  # > 0.75 ✅
                metadata='{}'
            )
        ]

        mock_db_connection.fetch.return_value = chunks_mixed_scores

        with patch('packages.ai_core.src.rag.notaire_rag.OllamaProvider') as mock_ollama:
            mock_ollama.return_value = mock_embedding_provider

            rag = NotaireRAG()
            rag._db_conn = mock_db_connection

            results = await rag.search("test query", threshold=0.75)

            # Seuls les chunks avec similarity >= 0.75 doivent être retournés
            assert len(results) == 2
            for result in results:
                assert result.similarity >= 0.75

    @pytest.mark.asyncio
    async def test_source_type_filter(self, mock_embedding_provider, mock_db_connection, sample_chunks):
        """Test que le filtre source_type='loi' ne retourne pas les chunks BOFIP."""
        from packages.ai_core.src.rag.notaire_rag import NotaireRAG

        mock_db_connection.fetch.return_value = [
            Mock(
                id=chunk['id'],
                source=chunk['source'],
                source_type=chunk['source_type'],
                content=chunk['content'],
                similarity=chunk['similarity'],
                metadata=json.dumps(chunk['metadata'])
            )
            for chunk in sample_chunks if chunk['source_type'] == 'loi'  # Filtrer côté "base"
        ]

        with patch('packages.ai_core.src.rag.notaire_rag.OllamaProvider') as mock_ollama:
            mock_ollama.return_value = mock_embedding_provider

            rag = NotaireRAG()
            rag._db_conn = mock_db_connection

            results = await rag.search("succession", source_type='loi')

            # Vérifications
            assert len(results) > 0
            for result in results:
                assert result.source_type == 'loi'
                assert result.source_type != 'bofip'

            # Vérifier que le filtre SQL a été appliqué
            sql_call = mock_db_connection.fetch.call_args[0][0]
            assert "AND source_type = $2" in sql_call


class TestNotaireRAGAnswer:
    """Tests de la méthode answer()."""

    @pytest.mark.asyncio
    async def test_answer_cites_sources(self, mock_ai_provider, sample_chunks):
        """Test que la réponse contient les numéros d'articles cités."""
        from packages.ai_core.src.rag.notaire_rag import NotaireRAG, ChunkResult, RAGResponse

        # Mock de la réponse IA avec citations
        mock_response = Mock()
        mock_response.content = """
        Selon l'article 734 du Code civil, les enfants succèdent à leurs parents sans distinction de sexe.
        L'abattement de 100 000€ s'applique selon les dispositions fiscales.
        """
        mock_ai_provider.complete.return_value = mock_response

        # Convertir les chunks en ChunkResult
        chunk_results = [
            ChunkResult(
                id=chunk['id'],
                source=chunk['source'],
                source_type=chunk['source_type'],
                content=chunk['content'],
                similarity=chunk['similarity'],
                metadata=chunk['metadata']
            )
            for chunk in sample_chunks
        ]

        with patch('packages.ai_core.src.rag.notaire_rag.get_ai_provider') as mock_get_provider:
            mock_get_provider.return_value = mock_ai_provider

            rag = NotaireRAG()

            response = await rag.answer(
                question="Quel est l'abattement pour un enfant en succession ?",
                chunks=chunk_results
            )

            # Vérifications
            assert isinstance(response, RAGResponse)
            assert "art. 734" in response.reponse or "article 734" in response.reponse
            assert len(response.sources_citees) > 0
            assert any("Code civil art.734" in source for source in response.sources_citees)

            # Vérifier que le provider IA a été appelé avec le bon prompt
            mock_ai_provider.complete.assert_called_once()
            call_args = mock_ai_provider.complete.call_args
            system_prompt = call_args[1]['system_prompt']
            assert "droit notarial français" in system_prompt
            assert "Code civil art.734" in str(call_args[0][0])  # Context dans les messages

    @pytest.mark.asyncio
    async def test_answer_with_context_dossier(self, mock_ai_provider, sample_chunks):
        """Test que le contexte dossier est intégré dans la réponse."""
        from packages.ai_core.src.rag.notaire_rag import NotaireRAG, ChunkResult

        mock_response = Mock()
        mock_response.content = "Réponse avec contexte du dossier"
        mock_ai_provider.complete.return_value = mock_response

        chunk_results = [ChunkResult(**chunk) for chunk in sample_chunks]

        with patch('packages.ai_core.src.rag.notaire_rag.get_ai_provider') as mock_get_provider:
            mock_get_provider.return_value = mock_ai_provider

            rag = NotaireRAG()

            context_dossier = "Succession de M. Martin, 3 enfants, patrimoine immobilier"

            response = await rag.answer(
                question="Comment répartir la succession ?",
                chunks=chunk_results,
                context_dossier=context_dossier
            )

            # Vérifier que le contexte dossier est inclus dans le prompt
            call_args = mock_ai_provider.complete.call_args[0][0]
            messages_str = str(call_args)
            assert "M. Martin" in messages_str
            assert "3 enfants" in messages_str

    @pytest.mark.asyncio
    async def test_answer_insufficient_context(self, mock_ai_provider):
        """Test de gestion du cas où le contexte est insuffisant."""
        from packages.ai_core.src.rag.notaire_rag import NotaireRAG, ChunkResult

        mock_response = Mock()
        mock_response.content = "Le contexte fourni est insuffisant pour répondre précisément à cette question."
        mock_ai_provider.complete.return_value = mock_response

        # Chunks peu pertinents
        irrelevant_chunks = [
            ChunkResult(
                id=str(uuid4()),
                source='Code civil art.999',
                source_type='loi',
                content='Article non pertinent pour la question',
                similarity=0.45,
                metadata={}
            )
        ]

        with patch('packages.ai_core.src.rag.notaire_rag.get_ai_provider') as mock_get_provider:
            mock_get_provider.return_value = mock_ai_provider

            rag = NotaireRAG()

            response = await rag.answer(
                question="Question très spécifique",
                chunks=irrelevant_chunks
            )

            assert "insuffisant" in response.reponse.lower()
            assert response.confiance < 0.7  # Faible confiance


class TestNotaireRAGComplete:
    """Tests de la méthode question_complete()."""

    @pytest.mark.asyncio
    async def test_question_complete_integration(self, mock_embedding_provider, mock_ai_provider, mock_db_connection, sample_chunks):
        """Test d'intégration search() + answer()."""
        from packages.ai_core.src.rag.notaire_rag import NotaireRAG

        # Mock search
        mock_db_connection.fetch.return_value = [
            Mock(
                id=chunk['id'],
                source=chunk['source'],
                source_type=chunk['source_type'],
                content=chunk['content'],
                similarity=chunk['similarity'],
                metadata=json.dumps(chunk['metadata'])
            )
            for chunk in sample_chunks
        ]

        # Mock answer
        mock_response = Mock()
        mock_response.content = "L'abattement pour un enfant est de 100 000€ selon l'article 779 CGI."
        mock_ai_provider.complete.return_value = mock_response

        with patch('packages.ai_core.src.rag.notaire_rag.OllamaProvider') as mock_ollama, \
             patch('packages.ai_core.src.rag.notaire_rag.get_ai_provider') as mock_get_provider:

            mock_ollama.return_value = mock_embedding_provider
            mock_get_provider.return_value = mock_ai_provider

            rag = NotaireRAG()
            rag._db_conn = mock_db_connection

            response = await rag.question_complete(
                question="Quel est l'abattement pour un enfant en succession ?",
                source_type='loi',
                k=5
            )

            # Vérifications
            assert "100 000" in response.reponse
            assert len(response.sources_citees) > 0
            assert response.confiance > 0.0

            # Vérifier que les deux méthodes ont été appelées
            mock_embedding_provider.embed.assert_called_once()
            mock_ai_provider.complete.assert_called_once()


class TestChunkResultModel:
    """Tests du modèle ChunkResult."""

    def test_chunk_result_creation(self):
        """Test de création d'un ChunkResult."""
        from packages.ai_core.src.rag.notaire_rag import ChunkResult

        chunk = ChunkResult(
            id="test-id",
            source="Code civil art.734",
            source_type="loi",
            content="Contenu de l'article",
            similarity=0.85,
            metadata={"article": 734}
        )

        assert chunk.id == "test-id"
        assert chunk.source == "Code civil art.734"
        assert chunk.source_type == "loi"
        assert chunk.similarity == 0.85
        assert chunk.metadata["article"] == 734

    def test_rag_response_creation(self):
        """Test de création d'une RAGResponse."""
        from packages.ai_core.src.rag.notaire_rag import RAGResponse

        response = RAGResponse(
            reponse="L'abattement est de 100 000€",
            sources_citees=["Code civil art.779"],
            confiance=0.9,
            avertissements=["Vérifier la date d'application"]
        )

        assert "100 000" in response.reponse
        assert "Code civil art.779" in response.sources_citees
        assert response.confiance == 0.9
        assert len(response.avertissements) == 1


# Fixtures de configuration pour les tests
@pytest.fixture(autouse=True)
def setup_test_environment():
    """Configure l'environnement de test."""
    import os
    os.environ['OLLAMA_BASE_URL'] = 'http://localhost:11434'
    os.environ['AI_PROVIDER'] = 'anthropic'  # Pour tester le fallback embeddings


if __name__ == "__main__":
    # Run des tests en mode standalone
    pytest.main([__file__, "-v"])