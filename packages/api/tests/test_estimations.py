#!/usr/bin/env python3
"""
Tests TDD pour le routeur d'estimations immobilières DVF.
Teste les 3 endpoints : stats, analyse, carte avec auth et cache Redis.
"""
import pytest
import httpx
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from decimal import Decimal

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Mocks pour les dépendances externes
@pytest.fixture
def mock_db_session():
    """Mock de session base de données."""
    session = Mock(spec=AsyncSession)
    return session

@pytest.fixture
def mock_redis():
    """Mock de client Redis."""
    client = Mock(spec=redis.Redis)
    client.get = AsyncMock(return_value=None)
    client.setex = AsyncMock()
    return client

@pytest.fixture
def mock_ai_provider():
    """Mock du provider IA."""
    provider = Mock()
    provider.generate_text = AsyncMock(return_value="""
    L'estimation de ce bien se situe dans une fourchette de 280 000€ à 320 000€.

    Facteurs positifs:
    - Zone recherchée avec bonne desserte
    - Surface attractive pour le marché
    - Typologie en demande

    Facteurs de correction:
    - Étage à considérer dans la valorisation
    - État général du bien à évaluer
    """)
    return provider

@pytest.fixture
def auth_headers():
    """Headers d'authentification pour les tests."""
    return {"Authorization": "Bearer test-token"}


class TestEstimationStats:
    """Tests pour GET /estimations/stats"""

    @pytest.mark.asyncio
    async def test_stats_returns_median_for_75008_appartement(self, mock_db_session, mock_redis):
        """Vérifie retour stats pour code postal 75008 Appartement."""
        # Mock des données de la vue estimation_stats
        mock_result = Mock()
        mock_result.first.return_value = Mock(
            code_postal="75008",
            type_bien="Appartement",
            prix_m2_median=8500,
            prix_m2_moyen=8750,
            prix_m2_min=6200,
            prix_m2_max=12000,
            nb_transactions=145,
            commune="Paris 8e Arrondissement",
            # Tendances simulées
            prix_m2_median_3mois=8300,
            prix_m2_median_12mois=7900,
            nb_transactions_3mois=35,
            nb_transactions_12mois=145
        )

        mock_db_session.execute.return_value = mock_result

        # Import et test endpoint
        from ..src.routers.estimations import get_estimation_stats

        result = await get_estimation_stats(
            code_postal="75008",
            type_bien="Appartement",
            db=mock_db_session,
            redis_client=mock_redis,
            current_user=Mock()
        )

        # Vérifications
        assert result.code_postal == "75008"
        assert result.type_bien == "Appartement"
        assert result.prix_m2_median == 8500
        assert result.nb_transactions == 145
        assert result.commune == "Paris 8e Arrondissement"

        # Vérifier tendances calculées
        assert result.tendance_3mois == pytest.approx(2.4, abs=0.1)  # +2.4%
        assert result.tendance_12mois == pytest.approx(7.6, abs=0.1)  # +7.6%

    @pytest.mark.asyncio
    async def test_stats_cache_redis_functionality(self, mock_db_session, mock_redis):
        """Vérifie que le cache Redis est utilisé correctement."""
        # Premier appel : cache miss
        mock_redis.get.return_value = None

        mock_result = Mock()
        mock_result.first.return_value = Mock(
            code_postal="75001",
            type_bien="Appartement",
            prix_m2_median=9500,
            prix_m2_moyen=9800,
            prix_m2_min=7000,
            prix_m2_max=15000,
            nb_transactions=89,
            commune="Paris 1er Arrondissement",
            prix_m2_median_3mois=9200,
            prix_m2_median_12mois=8800,
            nb_transactions_3mois=22,
            nb_transactions_12mois=89
        )

        mock_db_session.execute.return_value = mock_result

        from ..src.routers.estimations import get_estimation_stats

        # Premier appel
        result1 = await get_estimation_stats(
            code_postal="75001",
            type_bien="Appartement",
            db=mock_db_session,
            redis_client=mock_redis,
            current_user=Mock()
        )

        # Vérifier que setex a été appelé pour mise en cache
        mock_redis.setex.assert_called_once()
        cache_key = mock_redis.setex.call_args[0][0]
        assert "stats:75001:Appartement" in cache_key

        # Deuxième appel : cache hit
        cached_data = {
            "code_postal": "75001",
            "type_bien": "Appartement",
            "prix_m2_median": 9500,
            "prix_m2_moyen": 9800,
            "prix_m2_min": 7000,
            "prix_m2_max": 15000,
            "nb_transactions": 89,
            "commune": "Paris 1er Arrondissement",
            "tendance_3mois": 3.3,
            "tendance_12mois": 8.0
        }

        mock_redis.get.return_value = json.dumps(cached_data)
        mock_db_session.reset_mock()

        result2 = await get_estimation_stats(
            code_postal="75001",
            type_bien="Appartement",
            db=mock_db_session,
            redis_client=mock_redis,
            current_user=Mock()
        )

        # Vérifier que la DB n'a pas été appelée (cache hit)
        mock_db_session.execute.assert_not_called()
        assert result2.prix_m2_median == 9500

    @pytest.mark.asyncio
    async def test_stats_not_found_returns_404(self, mock_db_session, mock_redis):
        """Vérifie retour 404 si aucune donnée trouvée."""
        mock_result = Mock()
        mock_result.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        from ..src.routers.estimations import get_estimation_stats
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_estimation_stats(
                code_postal="99999",
                type_bien="Appartement",
                db=mock_db_session,
                redis_client=mock_redis,
                current_user=Mock()
            )

        assert exc_info.value.status_code == 404


class TestEstimationAnalyse:
    """Tests pour POST /estimations/analyse"""

    @pytest.mark.asyncio
    async def test_analyse_returns_fourchette_with_comparables(self, mock_db_session, mock_ai_provider):
        """Vérifie retour fourchette d'estimation avec comparables."""
        # Mock des transactions comparables
        mock_comparables = [
            Mock(
                id="comp-1",
                prix_vente=290000,
                surface_m2=62,
                prix_m2=4677,
                nb_pieces=3,
                date_vente=datetime(2024, 1, 15).date(),
                commune="Paris 8e",
                code_postal="75008",
                distance_km=0.3,
                score_similarite=0.92
            ),
            Mock(
                id="comp-2",
                prix_vente=315000,
                surface_m2=68,
                prix_m2=4632,
                nb_pieces=3,
                date_vente=datetime(2024, 2, 10).date(),
                commune="Paris 8e",
                code_postal="75008",
                distance_km=0.5,
                score_similarite=0.88
            )
        ]

        mock_result = Mock()
        mock_result.fetchall.return_value = mock_comparables
        mock_db_session.execute.return_value = mock_result

        # Mock insertion ai_interactions
        mock_db_session.execute = AsyncMock()
        mock_db_session.commit = AsyncMock()

        from ..src.routers.estimations import post_estimation_analyse

        request_data = {
            "adresse": "15 avenue Marceau, 75008 Paris",
            "type_bien": "Appartement",
            "surface_m2": 65,
            "nb_pieces": 3,
            "etage": 2,
            "annee_construction": 1980,
            "dossier_id": "dossier-123"
        }

        result = await post_estimation_analyse(
            request=Mock(**request_data),
            db=mock_db_session,
            current_user=Mock(id="user-123", email="notaire@test.fr"),
            ai_provider=mock_ai_provider
        )

        # Vérifications sur la fourchette
        assert result.fourchette.min >= 280000
        assert result.fourchette.max <= 320000
        assert result.fourchette.median > result.fourchette.min
        assert result.fourchette.median < result.fourchette.max

        # Vérifications sur les comparables
        assert len(result.comparables) == 2
        assert result.comparables[0]["id"] == "comp-1"

        # Vérifications sur le niveau de confiance
        assert result.niveau_confiance in ["fort", "moyen", "faible"]

        # Vérifier que l'IA a été appelée
        mock_ai_provider.generate_text.assert_called_once()

        # Vérifier logging ai_interactions
        assert mock_db_session.execute.call_count >= 2  # Comparables + log IA

    @pytest.mark.asyncio
    async def test_analyse_geocoding_integration(self, mock_db_session, mock_ai_provider):
        """Vérifie l'intégration du géocodage dans l'analyse."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock réponse BAN API
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "features": [{
                    "geometry": {
                        "coordinates": [2.3074, 48.8698]  # Coordonnées Champs-Élysées
                    }
                }]
            }
            mock_get.return_value.__aenter__.return_value = mock_response

            # Mock transactions dans un rayon de 500m
            mock_comparables = [
                Mock(
                    id="geo-1",
                    prix_vente=305000,
                    surface_m2=58,
                    prix_m2=5259,
                    latitude=48.8695,
                    longitude=2.3080,
                    distance_km=0.2,
                    score_similarite=0.89
                )
            ]

            mock_result = Mock()
            mock_result.fetchall.return_value = mock_comparables
            mock_db_session.execute.return_value = mock_result
            mock_db_session.commit = AsyncMock()

            from ..src.routers.estimations import post_estimation_analyse

            result = await post_estimation_analyse(
                request=Mock(
                    adresse="100 avenue des Champs-Élysées, 75008 Paris",
                    type_bien="Appartement",
                    surface_m2=60,
                    dossier_id=None
                ),
                db=mock_db_session,
                current_user=Mock(id="user-123"),
                ai_provider=mock_ai_provider
            )

            # Vérifier que le géocodage a été appelé
            mock_get.assert_called_once()

            # Vérifier que la recherche géographique est utilisée
            assert len(result.comparables) >= 1


class TestEstimationCarte:
    """Tests pour GET /estimations/carte"""

    @pytest.mark.asyncio
    async def test_carte_returns_geojson(self, mock_db_session):
        """Vérifie retour GeoJSON des transactions."""
        # Mock transactions avec coordonnées
        mock_transactions = [
            Mock(
                id="t1",
                longitude=2.3074,
                latitude=48.8698,
                prix_vente=285000,
                surface_m2=55,
                prix_m2=5182,
                type_bien="Appartement",
                date_vente=datetime(2024, 1, 15),
                adresse="8 rue de Rivoli, 75001 Paris"
            ),
            Mock(
                id="t2",
                longitude=2.3385,
                latitude=48.8606,
                prix_vente=420000,
                surface_m2=85,
                prix_m2=4941,
                type_bien="Appartement",
                date_vente=datetime(2024, 2, 20),
                adresse="25 rue Saint-Antoine, 75004 Paris"
            )
        ]

        mock_result = Mock()
        mock_result.fetchall.return_value = mock_transactions
        mock_db_session.execute.return_value = mock_result

        from ..src.routers.estimations import get_estimation_carte

        result = await get_estimation_carte(
            dept="75",
            type_bien="Appartement",
            db=mock_db_session,
            current_user=Mock()
        )

        # Vérifications format GeoJSON
        assert result.type == "FeatureCollection"
        assert len(result.features) == 2

        feature1 = result.features[0]
        assert feature1.type == "Feature"
        assert feature1.geometry.type == "Point"
        assert feature1.geometry.coordinates == [2.3074, 48.8698]
        assert feature1.properties["prix_m2"] == 5182
        assert feature1.properties["type_bien"] == "Appartement"

        # Vérifier métadonnées
        assert result.metadata["nb_transactions"] == 2
        assert result.metadata["departement"] == "75"


class TestAuthenticationRequired:
    """Tests de sécurité - authentification requise."""

    def test_stats_requires_auth_token(self):
        """Vérifie que stats retourne 401 sans token."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()

        # Import du router (simulation)
        from ..src.routers.estimations import router
        app.include_router(router)

        client = TestClient(app)

        # Appel sans token d'authentification
        response = client.get(
            "/estimations/stats",
            params={"code_postal": "75008", "type_bien": "Appartement"}
        )

        assert response.status_code == 401

    def test_analyse_requires_auth_token(self):
        """Vérifie que analyse retourne 401 sans token."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()

        from ..src.routers.estimations import router
        app.include_router(router)

        client = TestClient(app)

        response = client.post(
            "/estimations/analyse",
            json={
                "adresse": "15 avenue Marceau, 75008 Paris",
                "type_bien": "Appartement",
                "surface_m2": 65
            }
        )

        assert response.status_code == 401

    def test_carte_requires_auth_token(self):
        """Vérifie que carte retourne 401 sans token."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()

        from ..src.routers.estimations import router
        app.include_router(router)

        client = TestClient(app)

        response = client.get(
            "/estimations/carte",
            params={"dept": "75"}
        )

        assert response.status_code == 401


class TestCacheRedisIntegration:
    """Tests d'intégration du cache Redis."""

    @pytest.mark.asyncio
    async def test_cache_redis_deuxieme_appel_identique(self, mock_db_session, mock_redis):
        """Vérifie que le 2ème appel identique retourne le résultat en cache."""
        # Configuration cache pour simulation d'un hit
        cached_stats = {
            "code_postal": "75016",
            "type_bien": "Maison",
            "prix_m2_median": 12500,
            "prix_m2_moyen": 13200,
            "prix_m2_min": 9500,
            "prix_m2_max": 18000,
            "nb_transactions": 47,
            "commune": "Paris 16e Arrondissement",
            "tendance_3mois": -1.2,
            "tendance_12mois": 4.8
        }

        # Premier appel : cache miss puis mise en cache
        mock_redis.get.return_value = None

        mock_result = Mock()
        mock_result.first.return_value = Mock(**cached_stats)
        mock_db_session.execute.return_value = mock_result

        from ..src.routers.estimations import get_estimation_stats

        result1 = await get_estimation_stats(
            code_postal="75016",
            type_bien="Maison",
            db=mock_db_session,
            redis_client=mock_redis,
            current_user=Mock()
        )

        # Vérifier que setex a été appelé
        mock_redis.setex.assert_called_once()

        # Deuxième appel : cache hit
        mock_redis.get.return_value = json.dumps(cached_stats, default=str)
        mock_db_session.reset_mock()

        result2 = await get_estimation_stats(
            code_postal="75016",
            type_bien="Maison",
            db=mock_db_session,
            redis_client=mock_redis,
            current_user=Mock()
        )

        # Vérifications importantes
        assert result1.prix_m2_median == result2.prix_m2_median == 12500
        assert result1.nb_transactions == result2.nb_transactions == 47

        # Vérifier que la base n'a pas été interrogée au 2ème appel
        mock_db_session.execute.assert_not_called()

        # Vérifier que Redis get a été appelé 2 fois
        assert mock_redis.get.call_count == 2


class TestDataValidation:
    """Tests de validation des données."""

    @pytest.mark.asyncio
    async def test_stats_invalid_code_postal(self, mock_db_session, mock_redis):
        """Vérifie validation du code postal."""
        from ..src.routers.estimations import get_estimation_stats
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_estimation_stats(
                code_postal="ABC123",  # Code postal invalide
                type_bien="Appartement",
                db=mock_db_session,
                redis_client=mock_redis,
                current_user=Mock()
            )

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_analyse_surface_minimum(self, mock_db_session, mock_ai_provider):
        """Vérifie validation surface minimum."""
        from ..src.routers.estimations import post_estimation_analyse
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await post_estimation_analyse(
                request=Mock(
                    adresse="Test",
                    type_bien="Appartement",
                    surface_m2=2,  # Trop petit
                    dossier_id=None
                ),
                db=mock_db_session,
                current_user=Mock(),
                ai_provider=mock_ai_provider
            )

        assert exc_info.value.status_code == 422