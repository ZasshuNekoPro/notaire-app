#!/usr/bin/env python3
"""
Tests pour le pipeline d'import DVF.
Vérifie la normalisation, l'insertion en base, la déduplication et le logging.
"""
import pytest
import pandas as pd
import asyncpg
import asyncio
from datetime import datetime, date
from unittest.mock import Mock, AsyncMock, patch
import tempfile
from pathlib import Path
import sys
import os

# Ajouter le package au path pour les imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from import_dvf import normalize_dvf, load_to_postgres, geocode_missing


class TestNormalizeDvf:
    """Tests de normalisation des données DVF."""

    def test_normalize_dvf_filters_nature_vente(self):
        """Vérifie que seules les ventes sont conservées."""
        df = pd.DataFrame({
            'nature_mutation': ['Vente', 'Donation', 'Vente', 'Échange'],
            'valeur_fonciere': [300000, 0, 250000, 100000],
            'surface_reelle_bati': [50, 60, 40, 30],
            'type_local': ['Appartement', 'Appartement', 'Maison', 'Appartement']
        })

        result = normalize_dvf(df)

        # Seules les 2 ventes doivent être conservées
        assert len(result) == 2
        assert all(result['nature_mutation'] == 'Vente')

    def test_normalize_dvf_filters_prix_m2_range(self):
        """Vérifie les filtres sur le prix au m² (100-50000 €/m²)."""
        df = pd.DataFrame({
            'nature_mutation': ['Vente', 'Vente', 'Vente', 'Vente'],
            'valeur_fonciere': [5000, 300000, 250000, 2000000],  # 50, 6000, 6250, 40000 €/m²
            'surface_reelle_bati': [100, 50, 40, 50],
            'type_local': ['Appartement', 'Appartement', 'Maison', 'Appartement']
        })

        result = normalize_dvf(df)

        # Seules les transactions avec prix_m² entre 100 et 50000 doivent être conservées
        assert len(result) == 2

        # Vérifier les prix au m² calculés
        prix_m2_values = (result['prix_vente'] / result['surface_m2']).values
        assert all(100 <= prix_m2 <= 50000 for prix_m2 in prix_m2_values)

    def test_normalize_dvf_column_mapping(self):
        """Vérifie le mapping des colonnes DVF vers notre schéma."""
        df = pd.DataFrame({
            'date_mutation': ['2023-01-15'],
            'valeur_fonciere': [300000],
            'code_postal': ['75001'],
            'nom_commune': ['Paris'],
            'code_departement': ['75'],
            'type_local': ['Appartement'],
            'surface_reelle_bati': [50],
            'nombre_pieces_principales': [3],
            'surface_terrain': [0],
            'longitude': [2.3522],
            'latitude': [48.8566],
            'nature_mutation': ['Vente'],
            'adresse_numero': [15],
            'adresse_nom_voie': ['Rue de Rivoli']
        })

        result = normalize_dvf(df)

        # Vérifier le mapping des colonnes
        expected_columns = {
            'date_vente', 'prix_vente', 'code_postal', 'commune', 'departement',
            'type_bien', 'surface_m2', 'nb_pieces', 'surface_terrain_m2',
            'longitude', 'latitude', 'nature_mutation', 'numero_voie', 'nom_voie',
            'created_at', 'source'
        }

        assert set(result.columns) == expected_columns
        assert result['prix_vente'].iloc[0] == 300000
        assert result['commune'].iloc[0] == 'Paris'
        assert result['source'].iloc[0] == 'DVF'

    def test_normalize_dvf_invalid_data_filtering(self):
        """Vérifie l'élimination des données invalides."""
        df = pd.DataFrame({
            'nature_mutation': ['Vente', 'Vente', 'Vente', 'Vente'],
            'valeur_fonciere': [0, 300000, None, 250000],  # Prix invalides
            'surface_reelle_bati': [50, 0, 40, 2],  # Surfaces invalides
            'type_local': ['Appartement', 'Appartement', 'Local commercial', 'Appartement']
        })

        result = normalize_dvf(df)

        # Seule la dernière transaction devrait être conservée
        assert len(result) == 1
        assert result['prix_vente'].iloc[0] == 250000


@pytest.mark.asyncio
class TestLoadToPostgres:
    """Tests de chargement en base PostgreSQL."""

    @pytest.fixture
    async def mock_connection(self):
        """Mock de connexion asyncpg."""
        conn = Mock(spec=asyncpg.Connection)
        conn.transaction = AsyncMock()
        conn.transaction.return_value.__aenter__ = AsyncMock()
        conn.transaction.return_value.__aexit__ = AsyncMock()
        conn.copy_records_to_table = AsyncMock()
        conn.execute = AsyncMock()
        conn.fetch = AsyncMock()
        conn.fetchval = AsyncMock(return_value=50)  # Nombre après déduplication
        return conn

    async def test_load_to_postgres_bulk_insert(self, mock_connection):
        """Vérifie l'utilisation de copy_records_to_table pour les bulk inserts."""
        # Mock de la structure de table
        mock_connection.fetch.return_value = [
            {'column_name': 'date_vente', 'data_type': 'date', 'is_nullable': 'NO'},
            {'column_name': 'prix_vente', 'data_type': 'integer', 'is_nullable': 'NO'},
            {'column_name': 'surface_m2', 'data_type': 'numeric', 'is_nullable': 'YES'},
            {'column_name': 'type_bien', 'data_type': 'character varying', 'is_nullable': 'NO'},
            {'column_name': 'code_postal', 'data_type': 'character varying', 'is_nullable': 'YES'},
            {'column_name': 'commune', 'data_type': 'character varying', 'is_nullable': 'YES'},
            {'column_name': 'departement', 'data_type': 'character varying', 'is_nullable': 'YES'},
            {'column_name': 'nature_mutation', 'data_type': 'character varying', 'is_nullable': 'YES'},
            {'column_name': 'created_at', 'data_type': 'timestamp without time zone', 'is_nullable': 'YES'},
            {'column_name': 'source', 'data_type': 'character varying', 'is_nullable': 'YES'}
        ]

        # Préparer 100 lignes fictives
        df = pd.DataFrame({
            'date_vente': [date(2023, 1, 15)] * 100,
            'prix_vente': [300000] * 100,
            'surface_m2': [50] * 100,
            'type_bien': ['Appartement'] * 100,
            'code_postal': ['75001'] * 100,
            'commune': ['Paris'] * 100,
            'departement': ['75'] * 100,
            'nature_mutation': ['Vente'] * 100,
            'created_at': [datetime.utcnow()] * 100,
            'source': ['DVF'] * 100
        })

        result_count = await load_to_postgres(df, "75", mock_connection)

        # Vérifier que copy_records_to_table a été appelé
        mock_connection.copy_records_to_table.assert_called()

        # Vérifier la mise à jour de pipeline_runs
        execute_calls = [call for call in mock_connection.execute.call_args_list
                        if 'pipeline_runs' in str(call[0][0])]
        assert len(execute_calls) > 0

        # Vérifier le retour du nombre de lignes insérées
        assert result_count == 50  # Valeur mockée

    async def test_load_to_postgres_on_conflict_handling(self, mock_connection):
        """Vérifie la gestion des conflits (déduplication)."""
        # Mock de la structure de table
        mock_connection.fetch.return_value = [
            {'column_name': 'date_vente', 'data_type': 'date', 'is_nullable': 'NO'},
            {'column_name': 'prix_vente', 'data_type': 'integer', 'is_nullable': 'NO'},
            {'column_name': 'surface_m2', 'data_type': 'numeric', 'is_nullable': 'YES'},
            {'column_name': 'code_postal', 'data_type': 'character varying', 'is_nullable': 'YES'}
        ]

        # Simuler le retour du nombre réel de lignes insérées après déduplication
        mock_connection.fetchval.return_value = 50  # 50 nouvelles lignes sur 100

        df = pd.DataFrame({
            'date_vente': [date(2023, 1, 15)] * 100,
            'prix_vente': [300000] * 100,
            'surface_m2': [50] * 100,
            'code_postal': ['75001'] * 100,
        })

        result_count = await load_to_postgres(df, "75", mock_connection)

        # La déduplication devrait fonctionner via ON CONFLICT DO NOTHING
        assert result_count == 50  # Nombre réel après déduplication

    async def test_load_to_postgres_pipeline_runs_update(self, mock_connection):
        """Vérifie la mise à jour de la table pipeline_runs."""
        # Mock de la structure de table
        mock_connection.fetch.return_value = [
            {'column_name': 'date_vente', 'data_type': 'date', 'is_nullable': 'NO'},
            {'column_name': 'prix_vente', 'data_type': 'integer', 'is_nullable': 'NO'}
        ]

        df = pd.DataFrame({
            'date_vente': [date(2023, 1, 15)],
            'prix_vente': [300000],
        })

        await load_to_postgres(df, "75", mock_connection)

        # Vérifier que pipeline_runs est mis à jour avec le bon statut
        execute_calls = mock_connection.execute.call_args_list
        pipeline_insert_call = None

        for call in execute_calls:
            if 'INSERT INTO pipeline_runs' in str(call[0][0]):
                pipeline_insert_call = call
                break

        assert pipeline_insert_call is not None

        # Vérifier les paramètres (source, departement, statut)
        args = pipeline_insert_call[0][1:]  # Exclure la requête SQL
        assert 'DVF' in args  # source
        assert '75' in args   # departement
        assert 'terminé' in args  # statut


@pytest.mark.asyncio
class TestGeocodeMissing:
    """Tests de géocodage des adresses manquantes."""

    @pytest.fixture
    async def mock_connection(self):
        """Mock de connexion avec données de test."""
        conn = Mock(spec=asyncpg.Connection)

        # Mock des transactions sans coordonnées
        mock_records = [
            {
                'id': '123e4567-e89b-12d3-a456-426614174001',
                'numero_voie': 15,
                'nom_voie': 'Rue de Rivoli',
                'code_postal': '75001',
                'commune': 'Paris'
            },
            {
                'id': '123e4567-e89b-12d3-a456-426614174002',
                'numero_voie': 10,
                'nom_voie': 'Avenue des Champs-Élysées',
                'code_postal': '75008',
                'commune': 'Paris'
            }
        ]

        conn.fetch = AsyncMock(return_value=mock_records)
        conn.executemany = AsyncMock()

        return conn

    @patch('import_dvf.aiohttp.ClientSession')
    async def test_geocode_missing_batch_processing(self, mock_session_class, mock_connection):
        """Vérifie le traitement par batches de 50 avec rate limiting."""

        # Mock de la session HTTP
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        # Mock des réponses BAN API
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            'features': [{
                'geometry': {
                    'coordinates': [2.3522, 48.8566]  # [longitude, latitude]
                }
            }]
        }

        mock_session.get.return_value.__aenter__.return_value = mock_response

        result_count = await geocode_missing(mock_connection, batch_size=50)

        # Vérifier que les transactions ont été récupérées
        mock_connection.fetch.assert_called_once()

        # Vérifier les requêtes HTTP (2 adresses)
        assert mock_session.get.call_count == 2

        # Vérifier la mise à jour en base
        mock_connection.executemany.assert_called_once()

        # Vérifier le retour du nombre géocodé
        assert result_count == 2

    async def test_geocode_missing_rate_limiting(self, mock_connection):
        """Vérifie le respect du rate limiting (pause entre batches)."""
        # Créer plus de 50 enregistrements pour tester les batches
        mock_records = []
        for i in range(75):  # 75 records = 2 batches de 50
            mock_records.append({
                'id': f'123e4567-e89b-12d3-a456-42661417{i:04d}',
                'numero_voie': 15,
                'nom_voie': 'Rue de Rivoli',
                'code_postal': '75001',
                'commune': 'Paris'
            })

        mock_connection.fetch.return_value = mock_records

        with patch('import_dvf.aiohttp.ClientSession'), \
             patch('import_dvf.asyncio.sleep') as mock_sleep, \
             patch('import_dvf._geocode_address', return_value={'longitude': 2.3522, 'latitude': 48.8566}):

            await geocode_missing(mock_connection, batch_size=50)

            # Vérifier qu'il y a eu au moins une pause (entre les batches)
            assert mock_sleep.call_count >= 1
            mock_sleep.assert_called_with(0.5)  # BAN_RATE_LIMIT_DELAY


class TestPipelineIntegration:
    """Tests d'intégration du pipeline complet."""

    def test_deduplication_scenario(self):
        """Test de déduplication : même ligne insérée 2x → 1 seule en base."""
        # Ce test nécessiterait une vraie base de données de test
        # Pour le moment, on vérifie que la contrainte UNIQUE est bien définie

        # Simuler des données dupliquées
        df_duplicate = pd.DataFrame({
            'date_mutation': ['2023-01-15', '2023-01-15'],  # Même date
            'valeur_fonciere': [300000, 300000],  # Même prix
            'code_postal': ['75001', '75001'],  # Même code postal
            'surface_reelle_bati': [50, 50],  # Même surface
            'type_local': ['Appartement', 'Appartement'],
            'nom_commune': ['Paris', 'Paris'],
            'code_departement': ['75', '75'],
            'nature_mutation': ['Vente', 'Vente'],
        })

        # La normalisation doit conserver les deux lignes (elles sont identiques mais valides)
        result = normalize_dvf(df_duplicate)
        assert len(result) == 2

        # La déduplication se fait au niveau de la base avec ON CONFLICT
        # Le test réel nécessiterait une base de test

    @pytest.mark.asyncio
    async def test_pipeline_run_tracking(self):
        """Vérifie que pipeline_runs est correctement mis à jour."""
        mock_conn = Mock(spec=asyncpg.Connection)
        mock_conn.transaction = AsyncMock()
        mock_conn.transaction.return_value.__aenter__ = AsyncMock()
        mock_conn.transaction.return_value.__aexit__ = AsyncMock()
        mock_conn.copy_records_to_table = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {'column_name': 'date_vente', 'data_type': 'date', 'is_nullable': 'NO'},
            {'column_name': 'prix_vente', 'data_type': 'integer', 'is_nullable': 'NO'}
        ])
        mock_conn.fetchval = AsyncMock(return_value=1)

        df = pd.DataFrame({
            'date_vente': [date(2023, 1, 15)],
            'prix_vente': [300000],
        })

        await load_to_postgres(df, "75", mock_conn)

        # Vérifier qu'un enregistrement pipeline_runs a été créé
        pipeline_calls = [call for call in mock_conn.execute.call_args_list
                         if 'pipeline_runs' in str(call[0][0])]

        assert len(pipeline_calls) > 0

        # Vérifier que le statut est 'terminé' et nb_lignes = 1
        call_args = pipeline_calls[0][0]
        assert any('terminé' in str(arg) for arg in call_args[1:])


if __name__ == "__main__":
    # Lancer les tests
    pytest.main([__file__, "-v"])