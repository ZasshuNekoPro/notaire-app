#!/usr/bin/env python3
"""
Tests TDD pour le router actes notariaux
"""
import pytest
from httpx import AsyncClient
from unittest.mock import Mock, patch, AsyncMock
import json
import asyncio


@pytest.fixture
def notaire_token():
    """Token JWT pour un notaire"""
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJub3RhaXJlLWlkIiwicm9sZSI6Im5vdGFpcmUifQ.test"


@pytest.fixture
def sample_acte_vente():
    """Éléments d'un acte de vente pour tests"""
    return {
        "vendeur": {"nom": "Martin", "prenom": "Jean"},
        "acquereur": {"nom": "Dubois", "prenom": "Marie"},
        "bien": {
            "type": "appartement",
            "adresse": "123 rue de la Paix 75001 Paris",
            "surface": 85,
            "prix": 650000
        },
        "financement": "propre"
    }


class TestActesAnalyser:
    """Tests pour POST /actes/analyser"""

    @pytest.mark.asyncio
    async def test_acte_analyse_trouve_clauses_manquantes(self, client: AsyncClient, notaire_token: str, sample_acte_vente):
        """Test que l'analyse trouve les clauses obligatoires manquantes"""

        with patch('packages.ai_core.src.rag.get_notaire_rag') as mock_rag:
            mock_rag_instance = AsyncMock()
            mock_rag_instance.search.return_value = [
                Mock(
                    source="Code civil art.1583",
                    content="La vente est parfaite entre les parties dès qu'on est convenu de la chose et du prix",
                    similarity=0.9
                )
            ]
            mock_rag.return_value = mock_rag_instance

            response = await client.post(
                "/actes/analyser",
                json={
                    "type_acte": "VENTE",
                    "elements": sample_acte_vente
                },
                headers={"Authorization": f"Bearer {notaire_token}"}
            )

            assert response.status_code == 200
            data = response.json()

            # Vérifier la structure de réponse
            assert "structure_suggeree" in data
            assert "clauses_manquantes" in data
            assert "points_attention" in data
            assert "annexes_requises" in data
            assert "articles_loi" in data

            # Vérifier qu'il trouve des clauses manquantes pour un acte incomplet
            assert len(data["clauses_manquantes"]) > 0

            # Une vente doit contenir des mentions obligatoires
            clauses_str = str(data["clauses_manquantes"]).lower()
            assert any(word in clauses_str for word in ["diagnostic", "hypothèque", "servitude", "origine"])

    @pytest.mark.asyncio
    async def test_analyse_acte_succession(self, client: AsyncClient, notaire_token: str):
        """Test de l'analyse d'un acte de succession"""

        elements_succession = {
            "defunt": {"nom": "Durand", "date_deces": "2024-01-15"},
            "heritiers": [
                {"nom": "Durand", "prenom": "Pierre", "lien": "enfant", "part": 0.5},
                {"nom": "Martin", "prenom": "Julie", "lien": "enfant", "part": 0.5}
            ],
            "actif": {"total": 500000},
            "passif": {"total": 50000}
        }

        with patch('packages.ai_core.src.rag.get_notaire_rag') as mock_rag:
            mock_rag_instance = AsyncMock()
            mock_rag_instance.search.return_value = [
                Mock(
                    source="Code civil art.720",
                    content="Les successions s'ouvrent par la mort, au dernier domicile du défunt",
                    similarity=0.95
                )
            ]
            mock_rag.return_value = mock_rag_instance

            response = await client.post(
                "/actes/analyser",
                json={
                    "type_acte": "SUCC",
                    "elements": elements_succession
                },
                headers={"Authorization": f"Bearer {notaire_token}"}
            )

            assert response.status_code == 200
            data = response.json()

            # Pour une succession, on doit mentionner des éléments spécifiques
            articles = [article.lower() for article in data["articles_loi"]]
            assert any("720" in article for article in articles)

    @pytest.mark.asyncio
    async def test_analyse_type_acte_invalide(self, client: AsyncClient, notaire_token: str):
        """Test avec un type d'acte invalide"""

        response = await client.post(
            "/actes/analyser",
            json={
                "type_acte": "INVALIDE",
                "elements": {}
            },
            headers={"Authorization": f"Bearer {notaire_token}"}
        )

        assert response.status_code == 400
        assert "type d'acte non supporté" in response.json()["detail"].lower()


class TestActesRediger:
    """Tests pour POST /actes/rediger"""

    @pytest.mark.asyncio
    async def test_rediger_stream(self, client: AsyncClient, notaire_token: str, sample_acte_vente):
        """Test que SSE reçoit des chunks de texte"""

        async def mock_stream_generator():
            """Générateur mock pour simuler le streaming"""
            chunks = [
                "ACTE DE VENTE\n\n",
                "Par devant Maître...\n",
                "Ont comparu :\n",
                "- M. Jean MARTIN, vendeur\n",
                "- Mme Marie DUBOIS, acquéreur\n",
                "[À COMPLÉTER : conditions suspensives]\n",
                "En foi de quoi..."
            ]
            for chunk in chunks:
                yield chunk
                await asyncio.sleep(0.01)  # Petite pause pour simuler la latence

        with patch('packages.ai_core.src.providers.get_ai_provider') as mock_provider:
            mock_ai = AsyncMock()
            mock_ai.stream.return_value = mock_stream_generator()
            mock_provider.return_value = mock_ai

            response = await client.post(
                "/actes/rediger",
                json={
                    "type_acte": "VENTE",
                    "elements": sample_acte_vente,
                    "style": "formel"
                },
                headers={"Authorization": f"Bearer {notaire_token}"}
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

            # Lire le contenu SSE
            content = response.content.decode()

            # Vérifier que c'est du format SSE
            assert "data: " in content
            assert "ACTE DE VENTE" in content
            assert "Jean MARTIN" in content
            assert "[À COMPLÉTER" in content

    @pytest.mark.asyncio
    async def test_rediger_style_simplifie(self, client: AsyncClient, notaire_token: str):
        """Test de rédaction en style simplifié"""

        elements_donation = {
            "donateur": {"nom": "Leroy", "prenom": "Paul"},
            "donataire": {"nom": "Leroy", "prenom": "Anne"},
            "bien_donne": {"type": "somme", "montant": 50000},
            "lien_famille": "parent-enfant"
        }

        async def mock_simple_stream():
            chunks = [
                "DONATION\n\n",
                "M. Paul LEROY donne à sa fille Anne LEROY\n",
                "la somme de 50 000 euros.\n",
                "[À COMPLÉTER : conditions]"
            ]
            for chunk in chunks:
                yield chunk

        with patch('packages.ai_core.src.providers.get_ai_provider') as mock_provider:
            mock_ai = AsyncMock()
            mock_ai.stream.return_value = mock_simple_stream()
            mock_provider.return_value = mock_ai

            response = await client.post(
                "/actes/rediger",
                json={
                    "type_acte": "DON",
                    "elements": elements_donation,
                    "style": "simplifie"
                },
                headers={"Authorization": f"Bearer {notaire_token}"}
            )

            assert response.status_code == 200
            content = response.content.decode()

            # Le style simplifié doit être moins verbeux
            assert "DONATION" in content
            assert "50 000 euros" in content

    @pytest.mark.asyncio
    async def test_rediger_auth_required(self, client: AsyncClient):
        """Test que la rédaction nécessite une authentification"""

        response = await client.post(
            "/actes/rediger",
            json={
                "type_acte": "VENTE",
                "elements": {},
                "style": "formel"
            }
        )

        assert response.status_code == 401


class TestActesRelire:
    """Tests pour POST /actes/relire"""

    @pytest.mark.asyncio
    async def test_relire_retourne_score(self, client: AsyncClient, notaire_token: str):
        """Test que la relecture retourne un score de complétude"""

        contenu_acte = """
        ACTE DE VENTE

        Par devant Maître DUPONT, notaire...

        Ont comparu :
        M. Jean MARTIN, né le...
        Mme Marie DUBOIS, née le...

        Lequel vendeur vend à l'acquéreur qui accepte :
        Un appartement sis 123 rue de la Paix à Paris...

        Prix : 650 000 euros

        [Manque : diagnostics, origine de propriété]
        """

        with patch('packages.ai_core.src.providers.get_ai_provider') as mock_provider, \
             patch('packages.ai_core.src.rag.get_notaire_rag') as mock_rag:

            # Mock de la réponse d'analyse IA
            mock_ai = AsyncMock()
            mock_ai.complete.return_value = Mock(
                content=json.dumps({
                    "score_completude": 75,
                    "corrections": [
                        "Ajouter les diagnostics immobiliers obligatoires",
                        "Préciser l'origine de propriété"
                    ],
                    "risques_juridiques": [
                        "Absence de diagnostics peut entraîner la nullité"
                    ],
                    "clauses_manquantes": [
                        "Diagnostics amiante, plomb, DPE",
                        "Clause d'origine de propriété"
                    ]
                })
            )
            mock_provider.return_value = mock_ai

            # Mock du RAG pour les articles applicables
            mock_rag_instance = AsyncMock()
            mock_rag_instance.search.return_value = [
                Mock(
                    source="Code civil art.1602",
                    content="Le vendeur doit garantir l'acquéreur des vices cachés",
                    similarity=0.8
                )
            ]
            mock_rag.return_value = mock_rag_instance

            response = await client.post(
                "/actes/relire",
                json={
                    "contenu_acte": contenu_acte,
                    "type_acte": "VENTE"
                },
                headers={"Authorization": f"Bearer {notaire_token}"}
            )

            assert response.status_code == 200
            data = response.json()

            # Vérifier la structure de la réponse
            assert "score_completude" in data
            assert "corrections" in data
            assert "risques_juridiques" in data
            assert "clauses_manquantes" in data

            # Vérifier le score (0-100)
            assert 0 <= data["score_completude"] <= 100
            assert data["score_completude"] == 75

            # Vérifier qu'il y a des suggestions
            assert len(data["corrections"]) > 0
            assert len(data["clauses_manquantes"]) > 0

    @pytest.mark.asyncio
    async def test_relire_acte_complet_score_eleve(self, client: AsyncClient, notaire_token: str):
        """Test qu'un acte complet obtient un score élevé"""

        contenu_complet = """
        ACTE DE VENTE COMPLETE

        Toutes les mentions obligatoires sont présentes :
        - Diagnostics immobiliers
        - Origine de propriété
        - Servitudes
        - Hypothèques
        - Prix et modalités de paiement
        - Conditions suspensives
        """

        with patch('packages.ai_core.src.providers.get_ai_provider') as mock_provider:
            mock_ai = AsyncMock()
            mock_ai.complete.return_value = Mock(
                content=json.dumps({
                    "score_completude": 95,
                    "corrections": [],
                    "risques_juridiques": [],
                    "clauses_manquantes": []
                })
            )
            mock_provider.return_value = mock_ai

            response = await client.post(
                "/actes/relire",
                json={
                    "contenu_acte": contenu_complet,
                    "type_acte": "VENTE"
                },
                headers={"Authorization": f"Bearer {notaire_token}"}
            )

            assert response.status_code == 200
            data = response.json()

            assert data["score_completude"] >= 90
            assert len(data["corrections"]) == 0
            assert len(data["clauses_manquantes"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])