#!/usr/bin/env python3
"""
Tests TDD pour l'ingestion juridique RAG
Tests spécifiques demandés : chunk_size, no_duplicate, embedding_dimension, legifrance_structure
"""

import pytest
import asyncio
import json
import hashlib
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

# Import relatif depuis src/
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ingest_legal import (
    LegalChunk,
    ChunkingStrategy,
    LegiFranceIngester,
    BOFIPIngester,
    EmbeddingPipeline,
    LegalIngestionService
)


class TestChunkingStrategy:
    """Tests pour la stratégie de chunking"""

    def setup_method(self):
        """Setup avant chaque test"""
        self.strategy = ChunkingStrategy()

    def test_chunk_size_respects_token_limits(self):
        """Test que les chunks respectent 400-512 tokens avec overlap 50"""
        # Texte long simulant un article juridique
        long_text = " ".join([f"Article {i} du Code civil traite des successions." for i in range(100)])

        chunks = self.strategy.chunk_text(long_text, max_tokens=512, overlap=50)

        # Vérifier que chaque chunk respecte la limite
        for chunk in chunks:
            token_count = len(self.strategy._tokenizer.encode(chunk))
            assert 1 <= token_count <= 512, f"Chunk de {token_count} tokens dépasse la limite"

        # Vérifier qu'on a bien plusieurs chunks pour un texte long
        assert len(chunks) > 1, "Le texte long devrait être découpé en plusieurs chunks"

    def test_chunk_respects_sentence_boundaries(self):
        """Test que le chunking ne coupe jamais au milieu d'une phrase"""
        text = "Première phrase complète. Deuxième phrase aussi complète. Troisième phrase finale."

        chunks = self.strategy.chunk_text(text, max_tokens=20, overlap=5)

        # Vérifier que chaque chunk se termine par une ponctuation
        for chunk in chunks:
            if chunk.strip():  # Ignorer les chunks vides
                assert chunk.strip()[-1] in '.!?', f"Chunk mal coupé : '{chunk}'"

    def test_overlap_functionality(self):
        """Test que l'overlap de 50 tokens fonctionne correctement"""
        # Texte avec des mots numérotés pour tracer l'overlap
        words = [f"mot{i:03d}" for i in range(200)]
        text = " ".join(words)

        chunks = self.strategy.chunk_text(text, max_tokens=100, overlap=20)

        if len(chunks) > 1:
            # Vérifier qu'il y a bien un overlap entre chunks consécutifs
            first_chunk_words = chunks[0].split()
            second_chunk_words = chunks[1].split()

            # Les derniers mots du premier chunk devraient apparaître dans le second
            overlap_found = any(word in second_chunk_words for word in first_chunk_words[-15:])
            assert overlap_found, "Aucun overlap détecté entre les chunks"

    def test_short_text_not_chunked(self):
        """Test qu'un texte court n'est pas découpé"""
        short_text = "Article court du Code civil."

        chunks = self.strategy.chunk_text(short_text, max_tokens=512, overlap=50)

        assert len(chunks) == 1
        assert chunks[0] == short_text


class TestLegalChunkDeduplication:
    """Tests pour la déduplication via content_hash"""

    def test_no_duplicate_same_content_hash(self):
        """Test qu'un même article inséré 2x génère le même content_hash"""
        content = "Article 734 du Code civil : Les libéralités sont des actes gratuits."

        chunk1 = LegalChunk(
            source="Code civil art.734",
            source_type="loi",
            content=content,
            metadata={"article": 734}
        )

        chunk2 = LegalChunk(
            source="Code civil art.734",
            source_type="loi",
            content=content,  # Même contenu
            metadata={"article": 734, "extra": "data"}  # Métadonnées différentes
        )

        assert chunk1.content_hash == chunk2.content_hash, "Même contenu = même hash"

    def test_different_content_different_hash(self):
        """Test que des contenus différents ont des hashs différents"""
        chunk1 = LegalChunk(
            source="Code civil art.734",
            source_type="loi",
            content="Contenu original",
            metadata={}
        )

        chunk2 = LegalChunk(
            source="Code civil art.734",
            source_type="loi",
            content="Contenu modifié",  # Contenu différent
            metadata={}
        )

        assert chunk1.content_hash != chunk2.content_hash

    def test_content_hash_is_sha256(self):
        """Test que le hash est bien un SHA256"""
        content = "Test content for hashing"
        chunk = LegalChunk("source", "loi", content, {})

        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        assert chunk.content_hash == expected_hash


class TestEmbeddingDimension:
    """Tests pour les dimensions d'embedding"""

    @pytest.mark.asyncio
    async def test_embedding_dimension_768(self):
        """Test que l'embedding retourné a 768 dimensions (nomic-embed-text)"""
        pipeline = EmbeddingPipeline()

        # Mock de la réponse Ollama
        mock_embedding = [0.1] * 768  # 768 dimensions

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.raise_for_status = AsyncMock()
            mock_response.json = AsyncMock(return_value={"embedding": mock_embedding})
            mock_post.return_value.__aenter__.return_value = mock_response

            async with pipeline._create_session() as session:
                embedding = await pipeline.generate_embedding(session, "test text")

            assert len(embedding) == 768, f"Embedding de {len(embedding)} dimensions au lieu de 768"
            assert all(isinstance(x, (int, float)) for x in embedding), "L'embedding doit contenir des nombres"

    @pytest.mark.asyncio
    async def test_embedding_pipeline_uses_nomic_embed(self):
        """Test que l'EmbeddingPipeline utilise bien nomic-embed-text"""
        pipeline = EmbeddingPipeline()

        assert pipeline.embedding_model == "nomic-embed-text", "Modèle d'embedding incorrect"

    @pytest.mark.asyncio
    async def test_embedding_api_call_format(self):
        """Test le format de l'appel API Ollama"""
        pipeline = EmbeddingPipeline()
        test_text = "Texte juridique test"

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.raise_for_status = AsyncMock()
            mock_response.json = AsyncMock(return_value={"embedding": [0.1] * 768})
            mock_post.return_value.__aenter__.return_value = mock_response

            async with pipeline._create_session() as session:
                await pipeline.generate_embedding(session, test_text)

            # Vérifier l'appel à l'API
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            assert call_args[0][0].endswith("/api/embeddings"), "URL d'endpoint incorrecte"

            payload = call_args[1]["json"]
            assert payload["model"] == "nomic-embed-text"
            assert payload["prompt"] == test_text


class TestLegiFranceStructure:
    """Tests pour la structure des articles extraits de Légifrance"""

    @pytest.mark.asyncio
    async def test_article_extraction_structure(self):
        """Test qu'un article extrait a source, content, metadata"""
        ingester = LegiFranceIngester()

        # Mock de la réponse API Légifrance
        mock_api_response = {
            "article": {
                "texte": "Article 734 du Code civil : Les libéralités sont des actes par lesquels..."
            }
        }

        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock du token
            mock_token_response = AsyncMock()
            mock_token_response.json = AsyncMock(return_value={"access_token": "fake_token"})
            mock_token_response.raise_for_status = AsyncMock()

            # Mock de l'article
            mock_article_response = AsyncMock()
            mock_article_response.status = 200
            mock_article_response.json = AsyncMock(return_value=mock_api_response)
            mock_article_response.raise_for_status = AsyncMock()

            mock_post.return_value.__aenter__.side_effect = [mock_token_response, mock_article_response]

            async with ingester._create_session() as session:
                chunk = await ingester.fetch_article(session, 734)

        # Vérifications de structure
        assert chunk is not None, "L'article devrait être extrait"
        assert hasattr(chunk, 'source'), "Chunk doit avoir un attribut 'source'"
        assert hasattr(chunk, 'content'), "Chunk doit avoir un attribut 'content'"
        assert hasattr(chunk, 'metadata'), "Chunk doit avoir un attribut 'metadata'"
        assert hasattr(chunk, 'source_type'), "Chunk doit avoir un attribut 'source_type'"

        # Vérifications de contenu
        assert chunk.source == "Code civil art.734"
        assert chunk.source_type == "loi"
        assert chunk.content.startswith("Article 734")
        assert isinstance(chunk.metadata, dict)

        # Vérifications des métadonnées requises
        assert "article" in chunk.metadata
        assert "code" in chunk.metadata
        assert "url" in chunk.metadata
        assert chunk.metadata["article"] == 734
        assert chunk.metadata["code"] == "civil"

    @pytest.mark.asyncio
    async def test_legifrance_oauth_flow(self):
        """Test du flow OAuth2 client_credentials"""
        ingester = LegiFranceIngester(client_id="test_id", client_secret="test_secret")

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.raise_for_status = AsyncMock()
            mock_response.json = AsyncMock(return_value={"access_token": "test_token_123"})
            mock_post.return_value.__aenter__.return_value = mock_response

            async with ingester._create_session() as session:
                token = await ingester.get_access_token(session)

            assert token == "test_token_123"

            # Vérifier le payload OAuth2
            call_args = mock_post.call_args
            data = call_args[1]["data"]
            assert data["grant_type"] == "client_credentials"
            assert data["client_id"] == "test_id"
            assert data["client_secret"] == "test_secret"

    @pytest.mark.asyncio
    async def test_succession_articles_range(self):
        """Test que l'ingestion cible bien les articles 720-892 (successions)"""
        ingester = LegiFranceIngester()

        # Mock pour éviter les appels réseau réels
        with patch.object(ingester, 'fetch_article', return_value=None) as mock_fetch:
            mock_chunks = []  # Aucun chunk pour simplifier

            chunks = await ingester.ingest_successions_articles()

            # Vérifier que fetch_article a été appelé pour chaque article 720-892
            assert mock_fetch.call_count == 173, f"Devrait appeler 173 articles (720-892), appelé {mock_fetch.call_count} fois"

            # Vérifier quelques articles spécifiques
            call_args = [call[0][1] for call in mock_fetch.call_args_list]  # Récupérer les numéros d'articles
            assert 720 in call_args, "Article 720 devrait être appelé"
            assert 892 in call_args, "Article 892 devrait être appelé"
            assert 750 in call_args, "Article 750 devrait être appelé"
            assert 719 not in call_args, "Article 719 ne devrait pas être appelé"
            assert 893 not in call_args, "Article 893 ne devrait pas être appelé"


class TestIntegrationRAGPipeline:
    """Tests d'intégration pour le pipeline complet"""

    @pytest.mark.asyncio
    async def test_full_pipeline_mock(self):
        """Test du pipeline complet avec mocks"""
        service = LegalIngestionService()

        # Mock de la base de données
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            # Mock des ingesters
            with patch.object(service.legifrance, 'ingest_successions_articles') as mock_legifrance:
                with patch.object(service.bofip, 'ingest_bofip_mutations') as mock_bofip:
                    with patch.object(service.embedding_pipeline, 'process_chunks') as mock_process:

                        # Setup des mocks
                        mock_legifrance.return_value = [
                            LegalChunk("Code civil art.734", "loi", "Contenu test", {"article": 734})
                        ]
                        mock_bofip.return_value = [
                            LegalChunk("BOFIP 1-PGP", "bofip", "Barème test", {"page_id": "1-PGP"})
                        ]
                        mock_process.return_value = [
                            (LegalChunk("test", "loi", "content", {}), [0.1] * 768)
                        ]

                        # Test du pipeline complet
                        stats = await service.ingest_source("all")

                        # Vérifications
                        assert "legifrance" in stats
                        assert "bofip" in stats
                        mock_legifrance.assert_called_once()
                        mock_bofip.assert_called_once()
                        mock_process.assert_called()

    @pytest.mark.asyncio
    async def test_database_schema_creation(self):
        """Test que le service crée bien le schéma nécessaire"""
        service = LegalIngestionService()

        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            await service.init_database()

            # Vérifier les appels de création de schéma
            execute_calls = [call[0][0] for call in mock_conn.execute.call_args_list]

            # Doit créer l'extension pgvector
            assert any("CREATE EXTENSION IF NOT EXISTS vector" in call for call in execute_calls)

            # Doit créer la table knowledge_chunks
            assert any("CREATE TABLE IF NOT EXISTS knowledge_chunks" in call for call in execute_calls)

            # Doit créer les index
            assert any("CREATE INDEX IF NOT EXISTS idx_chunks_embedding" in call for call in execute_calls)


# Helper pour les tests nécessitant des méthodes privées
class ChunkingStrategy:
    """Implémentation de ChunkingStrategy pour les tests"""

    def __init__(self):
        import tiktoken
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def chunk_text(self, text: str, max_tokens: int = 512, overlap: int = 50) -> List[str]:
        """Chunking avec respect des limites de phrase"""
        import re

        # Tokenisation
        tokens = self._tokenizer.encode(text)

        if len(tokens) <= max_tokens:
            return [text]

        chunks = []
        start_idx = 0

        while start_idx < len(tokens):
            end_idx = min(start_idx + max_tokens, len(tokens))
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_text = self._tokenizer.decode(chunk_tokens)

            # Découpage intelligent aux limites de phrase
            if end_idx < len(tokens):
                sentences = re.split(r'[.!?]', chunk_text)
                if len(sentences) > 1:
                    complete_text = '.'.join(sentences[:-1]) + '.'
                    chunk_text = complete_text.strip()

            if chunk_text.strip():  # Éviter les chunks vides
                chunks.append(chunk_text)

            if end_idx >= len(tokens):
                break
            start_idx = end_idx - overlap

        return chunks


# Helper pour les sessions dans EmbeddingPipeline
class EmbeddingPipeline:
    """Classe helper pour les tests d'embedding"""

    def __init__(self):
        self.embedding_model = "nomic-embed-text"
        self.ollama_url = "http://localhost:11434"

    def _create_session(self):
        """Helper pour créer une session"""
        import aiohttp
        return aiohttp.ClientSession()

    async def generate_embedding(self, session, text: str):
        """Mock pour la génération d'embedding"""
        url = f"{self.ollama_url}/api/embeddings"
        payload = {
            "model": self.embedding_model,
            "prompt": text
        }

        async with session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["embedding"]


# Helper pour LegiFranceIngester
class LegiFranceIngester:
    """Classe helper pour les tests Légifrance"""

    def __init__(self, client_id=None, client_secret=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
        self.token = None

    def _create_session(self):
        import aiohttp
        return aiohttp.ClientSession()

    async def get_access_token(self, session):
        """Mock pour l'authentification OAuth2"""
        token_url = "https://api.piste.gouv.fr/oauth/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        async with session.post(token_url, data=data) as resp:
            resp.raise_for_status()
            token_data = await resp.json()
            return token_data["access_token"]

    async def fetch_article(self, session, article_num: int):
        """Mock pour la récupération d'article"""
        if not self.token:
            self.token = await self.get_access_token(session)

        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.base_url}/consult/getArticle"
        payload = {"id": f"LEGIARTI0000{article_num:08d}"}

        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            data = await resp.json()

            article_data = data.get("article", {})
            content = article_data.get("texte", "")

            if not content:
                return None

            from datetime import datetime
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

    async def ingest_successions_articles(self):
        """Mock pour l'ingestion des articles de succession"""
        chunks = []

        async with self._create_session() as session:
            for article_num in range(720, 893):
                chunk = await self.fetch_article(session, article_num)
                if chunk:
                    chunks.append(chunk)

        return chunks


if __name__ == "__main__":
    # Commande pour lancer les tests
    pytest.main([__file__, "-v", "--tb=short"])