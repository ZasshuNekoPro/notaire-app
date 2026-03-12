#!/usr/bin/env python3
"""
Tests pour le pipeline d'ingestion juridique et le système RAG

Tests couverts :
1. Création et découpage des chunks
2. Génération d'embeddings
3. Stockage en base avec déduplication
4. Recherche vectorielle RAG
5. Génération de réponses
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from typing import List

# Import des classes à tester
from packages.data_pipeline.src.ingest_legal import (
    LegalChunk,
    EmbeddingPipeline,
    LegalIngestionService
)
from packages.ai_core.src.rag.notaire_rag import (
    NotaireRAG,
    KnowledgeChunk,
    RAGResponse
)


class TestLegalChunk:
    """Tests pour la classe LegalChunk"""

    def test_content_hash_generation(self):
        """Test de génération du hash de contenu"""
        chunk = LegalChunk(
            source="Code civil art.734",
            source_type="loi",
            content="Article 734 du Code civil...",
            metadata={"article": 734}
        )

        # Le hash doit être reproductible
        hash1 = chunk.content_hash
        hash2 = chunk.content_hash
        assert hash1 == hash2

        # Le hash doit changer si le contenu change
        chunk2 = LegalChunk(
            source="Code civil art.734",
            source_type="loi",
            content="Article 734 du Code civil modifié...",
            metadata={"article": 734}
        )

        assert chunk.content_hash != chunk2.content_hash

    def test_content_hash_deduplication(self):
        """Test de déduplication basée sur le hash"""
        content = "Article 734 du Code civil..."

        chunk1 = LegalChunk("Source A", "loi", content, {})
        chunk2 = LegalChunk("Source B", "loi", content, {"different": True})

        # Même contenu = même hash, même si autres attributs différents
        assert chunk1.content_hash == chunk2.content_hash


class TestEmbeddingPipeline:
    """Tests pour le pipeline d'embeddings"""

    @pytest.fixture
    def embedding_pipeline(self):
        """Fixture pour le pipeline d'embeddings"""
        # Mock Ollama pour les tests
        pipeline = EmbeddingPipeline()
        pipeline.ollama_url = "http://mock-ollama:11434"
        return pipeline

    def test_chunk_content_single_chunk(self, embedding_pipeline):
        """Test découpage pour contenu court (pas de découpage nécessaire)"""
        content = "Court contenu qui tient en un seul chunk."
        chunks = embedding_pipeline.chunk_content(content)

        assert len(chunks) == 1
        assert chunks[0] == content

    def test_chunk_content_multiple_chunks(self, embedding_pipeline):
        """Test découpage pour contenu long"""
        # Créer un contenu artificiellement long
        long_content = "Article de loi. " * 100  # Répéter pour dépasser 512 tokens

        chunks = embedding_pipeline.chunk_content(long_content)

        # Doit créer plusieurs chunks
        assert len(chunks) > 1

        # Vérifier la cohérence
        for chunk in chunks:
            tokens = embedding_pipeline.tokenizer.encode(chunk)
            assert len(tokens) <= embedding_pipeline.max_tokens

    def test_chunk_content_sentence_boundaries(self, embedding_pipeline):
        """Test respect des frontières de phrase"""
        content = """Article 734. Première phrase complète. Deuxième phrase très longue qui continue sur plusieurs lignes et qui pourrait être coupée. Troisième phrase."""

        chunks = embedding_pipeline.chunk_content(content)

        # Les chunks doivent se terminer par des phrases complètes
        for chunk in chunks[:-1]:  # Sauf le dernier
            assert chunk.strip().endswith(('.', '!', '?'))

    @pytest.mark.asyncio
    async def test_generate_embedding_mock(self, embedding_pipeline):
        """Test génération d'embedding avec mock"""
        # Mock de la session HTTP
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3] * 256}  # 768 dimensions
        mock_session.post.return_value.__aenter__.return_value = mock_response

        embedding = await embedding_pipeline.generate_embedding(mock_session, "Test text")

        assert len(embedding) == 768
        assert all(isinstance(x, (int, float)) for x in embedding)

    @pytest.mark.asyncio
    async def test_process_chunks_integration(self, embedding_pipeline):
        """Test traitement complet avec mock"""
        # Données test
        legal_chunks = [
            LegalChunk("Code civil art.734", "loi", "Contenu de l'article 734", {}),
            LegalChunk("BOFIP 1-PGP", "bofip", "Contenu BOFIP", {})
        ]

        # Mock de l'embedding
        original_generate = embedding_pipeline.generate_embedding
        embedding_pipeline.generate_embedding = AsyncMock(return_value=[0.5] * 768)

        processed = await embedding_pipeline.process_chunks(legal_chunks)

        # Vérifications
        assert len(processed) == len(legal_chunks)
        for chunk, embedding in processed:
            assert isinstance(chunk, LegalChunk)
            assert len(embedding) == 768

        # Restaurer
        embedding_pipeline.generate_embedding = original_generate


class TestNotaireRAG:
    """Tests pour le service RAG"""

    @pytest.fixture
    def mock_db_connection(self):
        """Mock de connexion base de données"""
        mock_conn = AsyncMock()
        return mock_conn

    @pytest.fixture
    def notaire_rag(self):
        """Fixture pour NotaireRAG"""
        rag = NotaireRAG(
            db_url="postgresql://test:test@localhost/test",
            similarity_threshold=0.7
        )
        # Mock des providers
        rag.embedding_provider = AsyncMock()
        rag.llm_provider = AsyncMock()
        return rag

    @pytest.mark.asyncio
    async def test_embed_query(self, notaire_rag):
        """Test génération d'embedding pour une requête"""
        # Mock de l'embedding provider
        notaire_rag.embedding_provider.embed.return_value = [0.1, 0.2] * 384  # 768 dims

        embedding, time_ms = await notaire_rag.embed_query("Comment calculer les droits de succession ?")

        assert len(embedding) == 768
        assert time_ms > 0
        notaire_rag.embedding_provider.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_mock_db(self, notaire_rag, mock_db_connection):
        """Test recherche avec base de données mockée"""
        # Mock de la DB
        notaire_rag._get_db_connection = AsyncMock(return_value=mock_db_connection)

        # Mock résultats DB
        mock_rows = [
            {
                'id': 'chunk1-uuid',
                'source': 'Code civil art.734',
                'source_type': 'loi',
                'content': 'Contenu article 734...',
                'metadata': {'article': 734},
                'similarity': 0.85
            }
        ]
        mock_db_connection.fetch.return_value = mock_rows

        # Mock embedding
        notaire_rag.embed_query = AsyncMock(return_value=([0.5] * 768, 10.0))

        chunks, search_time = await notaire_rag.search(
            "droits de succession",
            source_type="loi",
            k=5
        )

        # Vérifications
        assert len(chunks) == 1
        chunk = chunks[0]
        assert isinstance(chunk, KnowledgeChunk)
        assert chunk.source == "Code civil art.734"
        assert chunk.similarity == 0.85
        assert search_time > 0

    @pytest.mark.asyncio
    async def test_answer_generation(self, notaire_rag):
        """Test génération de réponse"""
        # Chunks simulés
        chunks = [
            KnowledgeChunk(
                id="test-1",
                source="Code civil art.734",
                source_type="loi",
                content="Les droits de succession...",
                metadata={},
                similarity=0.9
            )
        ]

        # Mock du LLM provider
        notaire_rag.llm_provider.complete.return_value = "Selon l'article 734 du Code civil, les droits de succession..."

        answer, generation_time = await notaire_rag.answer(
            "Comment calculer les droits de succession ?",
            chunks
        )

        assert "Code civil" in answer
        assert generation_time > 0

    @pytest.mark.asyncio
    async def test_answer_no_chunks(self, notaire_rag):
        """Test réponse quand aucun chunk pertinent"""
        answer, time_ms = await notaire_rag.answer(
            "Question sans réponse",
            []
        )

        assert "ne trouve pas" in answer.lower()
        assert time_ms == 0

    def test_calculate_confidence(self, notaire_rag):
        """Test calcul du score de confiance"""
        # Cas avec chunks de qualité variable
        chunks_high = [
            KnowledgeChunk("1", "Source A", "loi", "Content", {}, 0.9),
            KnowledgeChunk("2", "Source B", "bofip", "Content", {}, 0.85)
        ]

        chunks_low = [
            KnowledgeChunk("3", "Source C", "loi", "Content", {}, 0.6)
        ]

        confidence_high = notaire_rag._calculate_confidence(chunks_high)
        confidence_low = notaire_rag._calculate_confidence(chunks_low)
        confidence_empty = notaire_rag._calculate_confidence([])

        assert confidence_high > confidence_low
        assert confidence_low > confidence_empty
        assert 0.0 <= confidence_high <= 1.0
        assert confidence_empty == 0.0

    @pytest.mark.asyncio
    async def test_query_full_pipeline(self, notaire_rag):
        """Test pipeline RAG complet"""
        # Mock de toutes les méthodes
        notaire_rag.embed_query = AsyncMock(return_value=([0.5] * 768, 5.0))
        notaire_rag.search = AsyncMock(return_value=([], 15.0))
        notaire_rag.answer = AsyncMock(return_value=("Réponse test", 50.0))

        response = await notaire_rag.query("Test question")

        # Vérifications
        assert isinstance(response, RAGResponse)
        assert response.answer == "Réponse test"
        assert response.query_embedding_time_ms == 5.0
        assert response.search_time_ms == 15.0
        assert response.generation_time_ms == 50.0

    @pytest.mark.asyncio
    async def test_rag_prompt_building(self, notaire_rag):
        """Test construction du prompt RAG"""
        chunks = [
            KnowledgeChunk(
                "1", "Code civil art.734", "loi",
                "Article 734 - Les droits de succession...", {}, 0.9
            ),
            KnowledgeChunk(
                "2", "BOFIP 3169", "bofip",
                "Calcul des droits...", {}, 0.85
            )
        ]

        prompt = notaire_rag._build_rag_prompt(
            "Comment calculer les droits de succession ?",
            chunks
        )

        # Le prompt doit contenir les sources
        assert "Code civil art.734" in prompt
        assert "BOFIP 3169" in prompt
        assert "Comment calculer les droits de succession ?" in prompt
        assert "notaire expert" in prompt.lower()
        assert "sources légales" in prompt.lower()


class TestLegalIngestionService:
    """Tests pour le service d'ingestion complet"""

    @pytest.fixture
    def ingestion_service(self):
        """Service d'ingestion avec mocks"""
        service = LegalIngestionService("postgresql://test:test@localhost/test")
        return service

    @pytest.mark.asyncio
    async def test_init_database_schema(self, ingestion_service):
        """Test initialisation du schéma de base"""
        mock_conn = AsyncMock()
        ingestion_service._get_db_connection = AsyncMock(return_value=mock_conn)

        conn = await ingestion_service.init_database()

        # Vérifier les appels SQL
        expected_calls = [
            "CREATE EXTENSION IF NOT EXISTS vector",
            "CREATE TABLE IF NOT EXISTS knowledge_chunks",
            "CREATE INDEX IF NOT EXISTS idx_chunks_embedding",
            "CREATE INDEX IF NOT EXISTS idx_chunks_source_type"
        ]

        for expected in expected_calls:
            # Vérifier que l'exécution contient le SQL attendu
            executed_sqls = [call[0][0] for call in mock_conn.execute.call_args_list]
            assert any(expected in sql for sql in executed_sqls), f"SQL '{expected}' non trouvé"


# Tests d'intégration (nécessitent Ollama et PostgreSQL)
@pytest.mark.integration
class TestRAGIntegration:
    """Tests d'intégration avec vraies dépendances"""

    @pytest.mark.asyncio
    async def test_embedding_real_ollama(self):
        """Test avec vrai Ollama (si disponible)"""
        pipeline = EmbeddingPipeline("http://localhost:11434")

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                embedding = await pipeline.generate_embedding(session, "Test d'embedding")
                assert len(embedding) == 768
        except Exception as e:
            pytest.skip(f"Ollama non disponible : {e}")

    @pytest.mark.asyncio
    async def test_rag_search_real_db(self):
        """Test avec vraie base PostgreSQL (si disponible)"""
        try:
            import asyncpg
            rag = NotaireRAG()
            stats = await rag.get_stats()
            assert "total_chunks" in stats
        except Exception as e:
            pytest.skip(f"PostgreSQL non disponible : {e}")


# Configuration pytest
def pytest_configure(config):
    """Configuration des marqueurs pytest"""
    config.addinivalue_line(
        "markers",
        "integration: tests nécessitant des services externes (PostgreSQL, Ollama)"
    )


if __name__ == "__main__":
    # Exécution directe
    pytest.main([__file__, "-v", "--tb=short"])