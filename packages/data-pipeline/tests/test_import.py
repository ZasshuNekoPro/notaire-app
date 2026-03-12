"""
Tests TDD pour le pipeline d'import DVF amélioré
ÉTAPE 1 — Tests avant implémentation
"""
import pytest
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncpg
from uuid import uuid4

# Mock des imports avant les vrais imports
sys_path_mock = MagicMock()
with patch.dict('sys.modules', {
    'src.import_dvf': sys_path_mock,
    'src.models': sys_path_mock
}):
    pass


# ============================================================
# CONFIGURATION TESTS
# ============================================================

@pytest.fixture
def sample_dvf_raw_data():
    """Données DVF brutes simulées."""
    return pd.DataFrame({
        'date_mutation': ['2024-01-15', '2024-02-20', '2024-03-10'],
        'valeur_fonciere': [520000, 680000, 450000],
        'code_postal': ['75008', '75008', '75011'],
        'nom_commune': ['Paris 8e', 'Paris 8e', 'Paris 11e'],
        'code_departement': ['75', '75', '75'],
        'type_local': ['Appartement', 'Appartement', 'Appartement'],
        'surface_reelle_bati': [65, 85, 55],
        'nombre_pieces_principales': [3, 4, 2],
        'surface_terrain': [None, None, None],
        'longitude': [2.308, 2.310, 2.371],
        'latitude': [48.875, 48.876, 48.863],
        'nature_mutation': ['Vente', 'Vente', 'Vente']
    })


@pytest.fixture
def sample_dvf_normalized():
    """Données DVF après normalisation attendue."""
    return pd.DataFrame({
        'date_vente': ['2024-01-15', '2024-02-20', '2024-03-10'],
        'prix_vente': [520000, 680000, 450000],
        'prix_m2': [8000, 8000, 8182],  # Calculé
        'surface_m2': [65.0, 85.0, 55.0],
        'type_bien': ['Appartement', 'Appartement', 'Appartement'],
        'nb_pieces': [3, 4, 2],
        'surface_terrain_m2': [None, None, None],
        'code_postal': ['75008', '75008', '75011'],
        'commune': ['Paris 8e', 'Paris 8e', 'Paris 11e'],
        'departement': ['75', '75', '75'],
        'longitude': [2.308, 2.310, 2.371],
        'latitude': [48.875, 48.876, 48.863],
        'nature_mutation': ['Vente', 'Vente', 'Vente']
    })


@pytest.fixture
def mock_postgres_conn():
    """Mock de la connexion PostgreSQL asyncpg."""
    conn = AsyncMock()
    conn.copy_records_to_table = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock(return_value=uuid4())
    return conn


@pytest.fixture
def mock_ban_api_response():
    """Mock de la réponse API BAN pour géocodage."""
    return {
        "features": [
            {
                "geometry": {
                    "coordinates": [2.308, 48.875]
                },
                "properties": {
                    "score": 0.95,
                    "label": "8 Boulevard du Port 75001 Paris"
                }
            }
        ]
    }


# ============================================================
# TESTS NORMALISATION DVF
# ============================================================

def test_normalize_dvf_columns_mapping(sample_dvf_raw_data):
    """Test que normalize_dvf() mappe correctement les colonnes."""
    from src.import_dvf import normalize_dvf

    result = normalize_dvf(sample_dvf_raw_data)

    # Vérifier le mapping des colonnes
    expected_columns = {
        'date_vente', 'prix_vente', 'code_postal', 'commune',
        'departement', 'type_bien', 'surface_m2', 'nb_pieces',
        'surface_terrain_m2', 'longitude', 'latitude', 'nature_mutation'
    }
    assert set(result.columns) >= expected_columns

    # Vérifier les valeurs mappées
    assert result['prix_vente'].tolist() == [520000, 680000, 450000]
    assert result['type_bien'].tolist() == ['Appartement', 'Appartement', 'Appartement']
    assert result['commune'].tolist() == ['Paris 8e', 'Paris 8e', 'Paris 11e']


def test_normalize_dvf_calculates_prix_m2(sample_dvf_raw_data):
    """Test que normalize_dvf() calcule le prix au m²."""
    from src.import_dvf import normalize_dvf

    result = normalize_dvf(sample_dvf_raw_data)

    # Vérifier le calcul prix_m2 = prix_vente / surface_m2
    assert 'prix_m2' in result.columns
    expected_prix_m2 = [8000, 8000, 8182]  # 520k/65, 680k/85, 450k/55

    for i, expected in enumerate(expected_prix_m2):
        assert abs(result['prix_m2'].iloc[i] - expected) < 10  # Tolérance arrondi


def test_normalize_dvf_filters_ventes_only(sample_dvf_raw_data):
    """Test que seules les ventes sont conservées."""
    # Ajouter des données non-vente
    dirty_data = sample_dvf_raw_data.copy()
    dirty_data.loc[len(dirty_data)] = {
        'date_mutation': '2024-04-01',
        'valeur_fonciere': 300000,
        'nature_mutation': 'Donation',  # Non-vente
        'type_local': 'Appartement',
        'surface_reelle_bati': 40,
        'code_postal': '75012',
        'nom_commune': 'Paris 12e',
        'code_departement': '75',
        'nombre_pieces_principales': 2,
        'longitude': 2.4,
        'latitude': 48.84
    }

    from src.import_dvf import normalize_dvf
    result = normalize_dvf(dirty_data)

    # Seules les 3 ventes doivent rester
    assert len(result) == 3
    assert all(result['nature_mutation'] == 'Vente')


def test_normalize_dvf_filters_invalid_prices():
    """Test que les prix invalides sont filtrés."""
    invalid_data = pd.DataFrame({
        'date_mutation': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'valeur_fonciere': [0, None, 80000000],  # Invalide: 0, null, trop élevé
        'nature_mutation': ['Vente', 'Vente', 'Vente'],
        'type_local': ['Appartement', 'Appartement', 'Appartement'],
        'surface_reelle_bati': [50, 60, 100],
        'code_postal': ['75001', '75002', '75003'],
        'nom_commune': ['Paris 1er', 'Paris 2e', 'Paris 3e'],
        'code_departement': ['75', '75', '75'],
        'nombre_pieces_principales': [2, 2, 4],
        'longitude': [2.3, 2.31, 2.32],
        'latitude': [48.86, 48.87, 48.85]
    })

    from src.import_dvf import normalize_dvf
    result = normalize_dvf(invalid_data)

    # Aucune ligne valide car tous les prix sont invalides
    assert len(result) == 0


def test_normalize_dvf_filters_invalid_surfaces():
    """Test que les surfaces invalides sont filtrées."""
    invalid_data = pd.DataFrame({
        'date_mutation': ['2024-01-01', '2024-01-02'],
        'valeur_fonciere': [400000, 500000],
        'nature_mutation': ['Vente', 'Vente'],
        'type_local': ['Appartement', 'Appartement'],
        'surface_reelle_bati': [0, None],  # Invalide: 0 et null
        'code_postal': ['75001', '75002'],
        'nom_commune': ['Paris 1er', 'Paris 2e'],
        'code_departement': ['75', '75'],
        'nombre_pieces_principales': [2, 3],
        'longitude': [2.3, 2.31],
        'latitude': [48.86, 48.87]
    })

    from src.import_dvf import normalize_dvf
    result = normalize_dvf(invalid_data)

    assert len(result) == 0


def test_normalize_dvf_filters_aberrant_prix_m2():
    """Test que les prix au m² aberrants sont filtrés."""
    aberrant_data = pd.DataFrame({
        'date_mutation': ['2024-01-01', '2024-01-02'],
        'valeur_fonciere': [100, 5000000],  # Prix/m² : 2€ et 50k€
        'nature_mutation': ['Vente', 'Vente'],
        'type_local': ['Appartement', 'Appartement'],
        'surface_reelle_bati': [50, 100],
        'code_postal': ['75001', '75002'],
        'nom_commune': ['Paris 1er', 'Paris 2e'],
        'code_departement': ['75', '75'],
        'nombre_pieces_principales': [2, 4],
        'longitude': [2.3, 2.31],
        'latitude': [48.86, 48.87]
    })

    from src.import_dvf import normalize_dvf
    result = normalize_dvf(aberrant_data)

    # Prix au m² hors bornes [100, 50000] → filtrés
    assert len(result) == 0


# ============================================================
# TESTS CHARGEMENT POSTGRESQL
# ============================================================

@pytest.mark.asyncio
async def test_load_to_postgres_uses_copy_bulk(sample_dvf_normalized, mock_postgres_conn):
    """Test que load_to_postgres() utilise COPY pour performance."""
    from src.import_dvf import load_to_postgres

    await load_to_postgres(sample_dvf_normalized, mock_postgres_conn)

    # Vérifier que COPY a été utilisé (pas INSERT)
    mock_postgres_conn.copy_records_to_table.assert_called_once()

    call_args = mock_postgres_conn.copy_records_to_table.call_args
    assert call_args[1]['table_name'] == 'transactions'
    assert 'records' in call_args[1]
    assert 'columns' in call_args[1]


@pytest.mark.asyncio
async def test_load_to_postgres_creates_pipeline_run(mock_postgres_conn):
    """Test que load_to_postgres() crée une entrée pipeline_runs."""
    from src.import_dvf import load_to_postgres

    sample_data = pd.DataFrame({
        'date_vente': ['2024-01-01'],
        'prix_vente': [400000],
        'departement': ['75']
    })

    await load_to_postgres(sample_data, mock_postgres_conn, departement='75')

    # Vérifier qu'une entrée pipeline_runs a été créée
    insert_calls = [call for call in mock_postgres_conn.execute.call_args_list
                   if 'pipeline_runs' in str(call)]
    assert len(insert_calls) >= 1


@pytest.mark.asyncio
async def test_load_to_postgres_handles_empty_dataframe(mock_postgres_conn):
    """Test gestion gracieuse des DataFrames vides."""
    from src.import_dvf import load_to_postgres

    empty_df = pd.DataFrame()

    await load_to_postgres(empty_df, mock_postgres_conn)

    # Ne doit pas appeler COPY avec un DataFrame vide
    mock_postgres_conn.copy_records_to_table.assert_not_called()


@pytest.mark.asyncio
async def test_load_to_postgres_updates_pipeline_status_on_error(mock_postgres_conn):
    """Test mise à jour du statut en cas d'erreur."""
    from src.import_dvf import load_to_postgres

    # Simuler une erreur lors du COPY
    mock_postgres_conn.copy_records_to_table.side_effect = Exception("COPY failed")

    sample_data = pd.DataFrame({'date_vente': ['2024-01-01'], 'prix_vente': [400000]})

    with pytest.raises(Exception):
        await load_to_postgres(sample_data, mock_postgres_conn, departement='75')

    # Vérifier que le statut d'erreur a été mis à jour
    error_calls = [call for call in mock_postgres_conn.execute.call_args_list
                  if 'erreur' in str(call).lower()]
    assert len(error_calls) >= 1


# ============================================================
# TESTS GÉOCODAGE BAN
# ============================================================

@pytest.mark.asyncio
async def test_geocode_transactions_batch_processing():
    """Test que le géocodage traite par batches de 50."""
    from src.import_dvf import geocode_transactions

    # Simuler 120 transactions sans coordonnées
    transactions_data = []
    for i in range(120):
        transactions_data.append({
            'id': uuid4(),
            'adresse': f"{i} rue Test",
            'code_postal': f"7500{i%10}",
            'commune': 'Paris',
            'longitude': None,
            'latitude': None
        })

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=transactions_data)
    mock_conn.execute = AsyncMock()

    with patch('src.import_dvf.geocode_address') as mock_geocode:
        mock_geocode.return_value = {'longitude': 2.3, 'latitude': 48.86}

        await geocode_transactions(mock_conn, batch_size=50)

        # Doit faire 3 batches (50 + 50 + 20)
        assert mock_geocode.call_count == 120

        # Vérifier les pauses entre batches
        # (difficile à tester directement, on vérifie au moins que ça termine)


@pytest.mark.asyncio
async def test_geocode_address_ban_api_success(mock_ban_api_response):
    """Test géocodage réussi via API BAN."""
    from src.import_dvf import geocode_address

    with patch('aiohttp.ClientSession.get') as mock_get:
        # Simuler réponse HTTP réussie
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_ban_api_response)
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await geocode_address("8 Boulevard du Port", "75001", "Paris")

        assert result['longitude'] == 2.308
        assert result['latitude'] == 48.875


@pytest.mark.asyncio
async def test_geocode_address_ban_api_no_results():
    """Test géocodage sans résultats de l'API BAN."""
    from src.import_dvf import geocode_address

    empty_response = {"features": []}

    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=empty_response)
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await geocode_address("Adresse Inexistante", "00000", "Nulle Part")

        assert result['longitude'] is None
        assert result['latitude'] is None


@pytest.mark.asyncio
async def test_geocode_address_ban_api_error():
    """Test gestion des erreurs de l'API BAN."""
    from src.import_dvf import geocode_address

    with patch('aiohttp.ClientSession.get') as mock_get:
        # Simuler erreur HTTP
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await geocode_address("Test", "75001", "Paris")

        # Doit retourner None en cas d'erreur (pas planter)
        assert result['longitude'] is None
        assert result['latitude'] is None


@pytest.mark.asyncio
async def test_geocode_transactions_skips_already_geocoded():
    """Test que le géocodage skip les transactions déjà géocodées."""
    from src.import_dvf import geocode_transactions

    # Transactions avec coordonnées existantes
    transactions_with_coords = [
        {
            'id': uuid4(),
            'adresse': 'Test',
            'code_postal': '75001',
            'commune': 'Paris',
            'longitude': 2.3,  # Déjà géocodé
            'latitude': 48.86
        }
    ]

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=transactions_with_coords)

    with patch('src.import_dvf.geocode_address') as mock_geocode:
        await geocode_transactions(mock_conn)

        # Ne doit pas appeler l'API BAN car déjà géocodé
        mock_geocode.assert_not_called()


# ============================================================
# TESTS INTÉGRATION PIPELINE COMPLET
# ============================================================

@pytest.mark.asyncio
async def test_import_department_full_pipeline():
    """Test d'intégration du pipeline complet pour un département."""
    from src.import_dvf import import_department

    with patch('src.import_dvf.download_dvf_data') as mock_download, \
         patch('src.import_dvf.normalize_dvf') as mock_normalize, \
         patch('src.import_dvf.load_to_postgres') as mock_load, \
         patch('src.import_dvf.geocode_transactions') as mock_geocode, \
         patch('asyncpg.connect') as mock_connect:

        # Configurer les mocks
        mock_download.return_value = pd.DataFrame({'test': [1, 2]})
        mock_normalize.return_value = pd.DataFrame({'normalized': [1, 2]})
        mock_load.return_value = None
        mock_geocode.return_value = None
        mock_connect.return_value.__aenter__.return_value = AsyncMock()

        await import_department('75')

        # Vérifier que toutes les étapes ont été appelées
        mock_download.assert_called_once_with('75')
        mock_normalize.assert_called_once()
        mock_load.assert_called_once()
        mock_geocode.assert_called_once()


def test_get_dvf_download_url():
    """Test génération URL de téléchargement DVF."""
    from src.import_dvf import get_dvf_download_url

    url_75 = get_dvf_download_url('75')
    url_92 = get_dvf_download_url('92')

    assert '75.csv' in url_75
    assert '92.csv' in url_92
    assert url_75.startswith('https://files.data.gouv.fr/')


def test_build_address_query():
    """Test construction requête adresse pour API BAN."""
    from src.import_dvf import build_address_query

    query = build_address_query("8 rue de la Paix", "75001", "Paris")
    expected = "8 rue de la Paix 75001 Paris"

    assert query == expected


# ============================================================
# TESTS PERFORMANCE ET EDGE CASES
# ============================================================

def test_normalize_dvf_performance_large_dataset():
    """Test performance sur un gros dataset simulé."""
    # Simuler 10k transactions
    large_data = pd.DataFrame({
        'date_mutation': ['2024-01-01'] * 10000,
        'valeur_fonciere': [400000] * 10000,
        'nature_mutation': ['Vente'] * 10000,
        'type_local': ['Appartement'] * 10000,
        'surface_reelle_bati': [50] * 10000,
        'code_postal': ['75008'] * 10000,
        'nom_commune': ['Paris 8e'] * 10000,
        'code_departement': ['75'] * 10000,
        'nombre_pieces_principales': [2] * 10000,
        'longitude': [2.3] * 10000,
        'latitude': [48.86] * 10000
    })

    import time
    start = time.time()

    from src.import_dvf import normalize_dvf
    result = normalize_dvf(large_data)

    duration = time.time() - start

    # Doit traiter 10k lignes en moins de 5 secondes
    assert duration < 5.0
    assert len(result) == 10000


def test_normalize_dvf_handles_missing_columns():
    """Test gestion des colonnes manquantes."""
    incomplete_data = pd.DataFrame({
        'date_mutation': ['2024-01-01'],
        'valeur_fonciere': [400000],
        'nature_mutation': ['Vente'],
        'type_local': ['Appartement'],
        'surface_reelle_bati': [50]
        # Colonnes manquantes : code_postal, commune, etc.
    })

    from src.import_dvf import normalize_dvf

    # Doit gérer gracieusement les colonnes manquantes
    try:
        result = normalize_dvf(incomplete_data)
        # Peut être vide si colonnes critiques manquent
        assert isinstance(result, pd.DataFrame)
    except KeyError as e:
        # Ou lever une erreur explicite si colonnes requises
        assert 'code_postal' in str(e) or 'nom_commune' in str(e)


# ============================================================
# TESTS CONFIGURATION
# ============================================================

def test_dvf_config_validation():
    """Test validation de la configuration DVF."""
    from src.import_dvf import validate_config

    # Config valide
    valid_config = {
        'BAN_API_URL': 'https://api-adresse.data.gouv.fr',
        'DVF_DATA_DIR': '/tmp/dvf',
        'BATCH_SIZE': 50
    }

    assert validate_config(valid_config) is True

    # Config invalide
    invalid_config = {
        'BAN_API_URL': '',  # URL vide
        'BATCH_SIZE': -1    # Taille négative
    }

    assert validate_config(invalid_config) is False