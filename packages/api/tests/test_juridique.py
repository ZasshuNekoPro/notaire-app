#!/usr/bin/env python3
"""
Tests TDD pour le router juridique
"""
import pytest
from httpx import AsyncClient
from unittest.mock import Mock, patch, AsyncMock
import json
from uuid import uuid4


@pytest.fixture
def sample_rag_response():
    """Réponse RAG simulée"""
    return Mock(
        reponse="Selon l'article 734 du Code civil, les enfants succèdent à leurs parents sans distinction de sexe. L'abattement applicable est de 100 000€ par enfant selon l'article 779 du CGI.",
        sources_citees=["Code civil art.734", "CGI art.779"],
        confiance=0.85,
        avertissements=[]
    )


@pytest.fixture
def notaire_token():
    """Token JWT pour un notaire"""
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJub3RhaXJlLWlkIiwicm9sZSI6Im5vdGFpcmUifQ.test"


class TestJuridiqueQuestion:
    """Tests pour POST /juridique/question"""

    @pytest.mark.asyncio
    async def test_question_cite_article(self, client: AsyncClient, notaire_token: str, sample_rag_response):
        """Test que la réponse mentionne l'article de loi"""

        with patch('packages.ai_core.src.rag.get_notaire_rag') as mock_rag:
            mock_rag_instance = AsyncMock()
            mock_rag_instance.question_complete.return_value = sample_rag_response
            mock_rag.return_value = mock_rag_instance

            response = await client.post(
                "/juridique/question",
                json={
                    "question": "Quel est l'abattement pour un enfant en succession ?",
                    "source_types": ["loi"]
                },
                headers={"Authorization": f"Bearer {notaire_token}"}
            )

            assert response.status_code == 200
            data = response.json()

            # Vérifier que la réponse contient l'article
            assert "art. 734" in data["reponse"] or "article 734" in data["reponse"]
            assert "100 000" in data["reponse"]
            assert len(data["sources_citees"]) > 0
            assert data["confiance"] > 0.8

            # Vérifier que le RAG a été appelé avec les bons paramètres
            mock_rag_instance.question_complete.assert_called_once()
            call_args = mock_rag_instance.question_complete.call_args
            assert "abattement" in call_args.kwargs["question"]

    @pytest.mark.asyncio
    async def test_question_avec_dossier_id(self, client: AsyncClient, notaire_token: str, sample_rag_response):
        """Test que la question est sauvegardée dans le dossier si ID fourni"""

        dossier_id = str(uuid4())

        with patch('packages.ai_core.src.rag.get_notaire_rag') as mock_rag, \
             patch('packages.api.src.services.juridique_service.save_ai_interaction') as mock_save:

            mock_rag_instance = AsyncMock()
            mock_rag_instance.question_complete.return_value = sample_rag_response
            mock_rag.return_value = mock_rag_instance

            response = await client.post(
                "/juridique/question",
                json={
                    "question": "Question test",
                    "dossier_id": dossier_id
                },
                headers={"Authorization": f"Bearer {notaire_token}"}
            )

            assert response.status_code == 200

            # Vérifier que l'interaction a été sauvegardée
            mock_save.assert_called_once()
            save_args = mock_save.call_args
            assert save_args.kwargs["dossier_id"] == dossier_id
            assert "Question test" in save_args.kwargs["question"]

    @pytest.mark.asyncio
    async def test_question_auth_required(self, client: AsyncClient):
        """Test que l'authentification est requise"""

        response = await client.post(
            "/juridique/question",
            json={"question": "Test sans auth"}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_question_role_clerc_autorise(self, client: AsyncClient):
        """Test qu'un clerc peut poser des questions"""

        clerc_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJjbGVyYy1pZCIsInJvbGUiOiJjbGVyYyJ9.test"

        with patch('packages.ai_core.src.rag.get_notaire_rag') as mock_rag:
            mock_rag_instance = AsyncMock()
            mock_rag_instance.question_complete.return_value = Mock(
                reponse="Réponse test",
                sources_citees=[],
                confiance=0.5,
                avertissements=[]
            )
            mock_rag.return_value = mock_rag_instance

            response = await client.post(
                "/juridique/question",
                json={"question": "Question clerc"},
                headers={"Authorization": f"Bearer {clerc_token}"}
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_question_validation_error(self, client: AsyncClient, notaire_token: str):
        """Test que les erreurs de validation sont correctement gérées"""

        response = await client.post(
            "/juridique/question",
            json={},  # Question manquante
            headers={"Authorization": f"Bearer {notaire_token}"}
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_question_rag_error(self, client: AsyncClient, notaire_token: str):
        """Test de gestion d'erreur du RAG"""

        with patch('packages.ai_core.src.rag.get_notaire_rag') as mock_rag:
            mock_rag_instance = AsyncMock()
            mock_rag_instance.question_complete.side_effect = Exception("Erreur RAG")
            mock_rag.return_value = mock_rag_instance

            response = await client.post(
                "/juridique/question",
                json={"question": "Question test"},
                headers={"Authorization": f"Bearer {notaire_token}"}
            )

            assert response.status_code == 500
            data = response.json()
            assert "erreur" in data["detail"].lower()


class TestJuridiqueStats:
    """Tests pour GET /juridique/stats"""

    @pytest.mark.asyncio
    async def test_stats_public(self, client: AsyncClient):
        """Test que les stats sont accessibles publiquement"""

        with patch('packages.ai_core.src.rag.get_notaire_rag') as mock_rag:
            mock_rag_instance = AsyncMock()
            mock_rag_instance.get_stats.return_value = {
                "total_chunks": 1250,
                "by_source_type": {
                    "loi": 800,
                    "bofip": 350,
                    "jurisprudence": 100
                }
            }
            mock_rag.return_value = mock_rag_instance

            response = await client.get("/juridique/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["total_chunks"] == 1250
            assert "loi" in data["by_source_type"]
            assert data["by_source_type"]["loi"] == 800


if __name__ == "__main__":
    pytest.main([__file__, "-v"])