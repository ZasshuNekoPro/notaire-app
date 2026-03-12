#!/usr/bin/env python3
"""
Pipeline d'import DVF pour l'estimation immobilière notariale.
Étapes : téléchargement → normalisation → bulk insert → géocodage BAN.
"""
import asyncio
import argparse
import logging
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
import tempfile
import gzip
import time

import pandas as pd
import asyncpg
import aiohttp
from urllib.parse import quote_plus

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration DVF
DVF_BASE_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv"
BAN_API_URL = "https://api-adresse.data.gouv.fr/search"
BAN_BATCH_SIZE = 50
BAN_RATE_LIMIT_DELAY = 0.5  # 500ms entre batches

# Mapping des colonnes DVF vers notre schéma
COLUMNS_MAP = {
    "date_mutation": "date_vente",
    "valeur_fonciere": "prix_vente",
    "code_postal": "code_postal",
    "nom_commune": "commune",
    "code_departement": "departement",
    "type_local": "type_bien",
    "surface_reelle_bati": "surface_m2",
    "nombre_pieces_principales": "nb_pieces",
    "surface_terrain": "surface_terrain_m2",
    "longitude": "longitude",
    "latitude": "latitude",
    "nature_mutation": "nature_mutation",
    "adresse_numero": "numero_voie",
    "adresse_suffixe": "suffixe_voie",
    "adresse_nom_voie": "nom_voie",
}

# Filtres de qualité DVF
VALID_NATURE_MUTATIONS = ["Vente"]
VALID_TYPE_BIENS = [
    "Appartement",
    "Maison",
    "Local industriel. commercial ou assimilé",
    "Dépendance"
]
MIN_PRIX_VENTE = 1000  # €
MIN_SURFACE_M2 = 5     # m²
MIN_PRIX_M2 = 100      # €/m²
MAX_PRIX_M2 = 50000    # €/m²


async def download_dvf(departement: str, session: aiohttp.ClientSession) -> Path:
    """Télécharge le fichier DVF pour un département donné."""
    url = f"{DVF_BASE_URL}/{departement}.csv.gz"

    logger.info(f"Téléchargement DVF pour le département {departement}...")

    async with session.get(url) as response:
        if response.status != 200:
            raise ValueError(f"Échec téléchargement DVF {departement}: {response.status}")

        # Créer fichier temporaire
        temp_file = Path(tempfile.mktemp(suffix=f"_dvf_{departement}.csv.gz"))

        with open(temp_file, 'wb') as f:
            async for chunk in response.content.iter_chunked(8192):
                f.write(chunk)

    logger.info(f"DVF {departement} téléchargé: {temp_file}")
    return temp_file


def normalize_dvf(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise les données DVF : mapping colonnes + filtres qualité.

    Args:
        df: DataFrame DVF brut

    Returns:
        DataFrame normalisé et filtré
    """
    logger.info(f"Normalisation de {len(df)} transactions DVF...")

    # Mapping des colonnes
    available_cols = {k: v for k, v in COLUMNS_MAP.items() if k in df.columns}
    df_clean = df[list(available_cols.keys())].rename(columns=available_cols)

    # Conversion des types
    if 'prix_vente' in df_clean.columns:
        df_clean['prix_vente'] = pd.to_numeric(df_clean['prix_vente'], errors='coerce')

    if 'surface_m2' in df_clean.columns:
        df_clean['surface_m2'] = pd.to_numeric(df_clean['surface_m2'], errors='coerce')

    if 'nb_pieces' in df_clean.columns:
        df_clean['nb_pieces'] = pd.to_numeric(df_clean['nb_pieces'], errors='coerce')

    if 'surface_terrain_m2' in df_clean.columns:
        df_clean['surface_terrain_m2'] = pd.to_numeric(df_clean['surface_terrain_m2'], errors='coerce')

    if 'date_vente' in df_clean.columns:
        df_clean['date_vente'] = pd.to_datetime(df_clean['date_vente'], errors='coerce')

    # Filtres de qualité
    initial_count = len(df_clean)

    # 1. Nature mutation = "Vente" uniquement
    if 'nature_mutation' in df_clean.columns:
        df_clean = df_clean[df_clean['nature_mutation'].isin(VALID_NATURE_MUTATIONS)]

    # 2. Type de bien valide
    if 'type_bien' in df_clean.columns:
        df_clean = df_clean[df_clean['type_bien'].isin(VALID_TYPE_BIENS)]

    # 3. Prix > seuil minimum
    if 'prix_vente' in df_clean.columns:
        df_clean = df_clean[
            (df_clean['prix_vente'] > MIN_PRIX_VENTE) &
            (df_clean['prix_vente'].notna())
        ]

    # 4. Surface > seuil minimum
    if 'surface_m2' in df_clean.columns:
        df_clean = df_clean[
            (df_clean['surface_m2'] > MIN_SURFACE_M2) &
            (df_clean['surface_m2'].notna())
        ]

    # 5. Prix au m² dans la fourchette acceptable
    if 'prix_vente' in df_clean.columns and 'surface_m2' in df_clean.columns:
        df_clean['prix_m2'] = df_clean['prix_vente'] / df_clean['surface_m2']
        df_clean = df_clean[
            (df_clean['prix_m2'] >= MIN_PRIX_M2) &
            (df_clean['prix_m2'] <= MAX_PRIX_M2)
        ]

    # Supprimer les colonnes temporaires
    if 'prix_m2' in df_clean.columns:
        df_clean = df_clean.drop(columns=['prix_m2'])

    # Ajouter métadonnées
    df_clean['created_at'] = datetime.utcnow()
    df_clean['source'] = 'DVF'

    final_count = len(df_clean)
    rejected_count = initial_count - final_count

    logger.info(f"Normalisation terminée: {final_count} transactions conservées "
                f"({rejected_count} rejetées, {final_count/initial_count*100:.1f}% retention)")

    return df_clean


async def load_to_postgres(df: pd.DataFrame, dept: str, conn: asyncpg.Connection) -> int:
    """
    Charge les données DVF en base via COPY (bulk insert optimisé) avec déduplication.

    Args:
        df: DataFrame normalisé
        dept: Code département
        conn: Connexion asyncpg

    Returns:
        Nombre de lignes effectivement insérées (après déduplication)
    """
    if len(df) == 0:
        logger.warning("Aucune transaction à charger")
        return 0

    logger.info(f"Chargement de {len(df)} transactions en base...")
    start_time = datetime.utcnow()

    # Début de transaction
    async with conn.transaction():
        try:
            # 1. Créer une table temporaire pour le bulk insert
            temp_table = f"temp_transactions_{dept}_{int(time.time())}"

            # Récupérer la structure de la table transactions
            columns_info = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'transactions'
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """)

            # Construire la définition de la table temporaire
            temp_columns = []
            for col_info in columns_info:
                col_name = col_info['column_name']
                if col_name == 'id':
                    continue  # On skip l'ID auto-généré

                data_type = col_info['data_type']
                nullable = "NULL" if col_info['is_nullable'] == 'YES' else "NOT NULL"

                # Mapper les types PostgreSQL
                if data_type == 'character varying':
                    data_type = 'VARCHAR(255)'
                elif data_type == 'timestamp without time zone':
                    data_type = 'TIMESTAMP'
                elif data_type == 'uuid':
                    continue  # Skip UUID columns pour l'import

                temp_columns.append(f"{col_name} {data_type}")

            # Créer la table temporaire
            create_temp_sql = f"""
                CREATE TEMP TABLE {temp_table} (
                    {', '.join(temp_columns)}
                )
            """
            await conn.execute(create_temp_sql)

            # 2. Préparer les données pour COPY
            # Filtrer les colonnes qui existent dans la table
            existing_columns = [col_info['column_name'] for col_info in columns_info
                              if col_info['column_name'] != 'id']
            df_filtered = df.reindex(columns=existing_columns, fill_value=None)

            # Convertir en records
            records = []
            for _, row in df_filtered.iterrows():
                record = []
                for col in df_filtered.columns:
                    value = row[col]
                    # Gestion des valeurs NaN/None
                    if pd.isna(value):
                        record.append(None)
                    elif isinstance(value, pd.Timestamp):
                        record.append(value.to_pydatetime())
                    else:
                        record.append(value)
                records.append(tuple(record))

            # 3. Bulk insert dans la table temporaire
            await conn.copy_records_to_table(
                temp_table,
                records=records,
                columns=list(df_filtered.columns)
            )

            # 4. Insert avec ON CONFLICT DO NOTHING pour déduplication
            # Définir les colonnes de déduplication
            dedup_columns = ['date_vente', 'prix_vente', 'code_postal', 'surface_m2']

            # Construire la requête INSERT avec ON CONFLICT
            insert_columns = [col for col in df_filtered.columns if col in existing_columns]
            placeholders = ', '.join(insert_columns)

            insert_sql = f"""
                INSERT INTO transactions ({placeholders})
                SELECT {placeholders}
                FROM {temp_table}
                ON CONFLICT (date_vente, prix_vente, code_postal, surface_m2)
                DO NOTHING
            """

            # Exécuter l'insertion avec déduplication
            await conn.execute(insert_sql)

            # 5. Compter les lignes effectivement insérées
            count_sql = f"""
                SELECT COUNT(*) FROM transactions t1
                WHERE EXISTS (
                    SELECT 1 FROM {temp_table} t2
                    WHERE t1.date_vente = t2.date_vente
                    AND t1.prix_vente = t2.prix_vente
                    AND t1.code_postal = t2.code_postal
                    AND t1.surface_m2 = t2.surface_m2
                )
            """
            actual_inserted = await conn.fetchval(count_sql)

            # 6. Enregistrer dans pipeline_runs avec la structure correcte de la table
            await conn.execute("""
                INSERT INTO pipeline_runs (
                    source,
                    departement,
                    statut,
                    nb_lignes,
                    started_at,
                    finished_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
                'DVF',
                dept,
                'terminé',
                actual_inserted,
                start_time,
                datetime.utcnow()
            )

            logger.info(f"✅ {actual_inserted}/{len(df)} nouvelles transactions insérées "
                       f"({len(df) - actual_inserted} doublons détectés)")

            return actual_inserted

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            # Enregistrer l'erreur dans pipeline_runs
            await conn.execute("""
                INSERT INTO pipeline_runs (
                    source,
                    departement,
                    statut,
                    nb_lignes,
                    erreur,
                    started_at,
                    finished_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                'DVF',
                dept,
                'erreur',
                0,
                str(e),
                start_time,
                datetime.utcnow()
            )
            raise


async def geocode_missing(conn: asyncpg.Connection, batch_size: int = 50) -> int:
    """
    Géocode les transactions sans coordonnées via l'API BAN.

    Args:
        conn: Connexion asyncpg
        batch_size: Taille des batches (défaut: 50)

    Returns:
        Nombre d'adresses géocodées avec succès
    """
    logger.info("Démarrage du géocodage des adresses manquantes...")

    # Récupérer les transactions sans coordonnées (limite 500)
    query = """
        SELECT id, numero_voie, nom_voie, code_postal, commune
        FROM transactions
        WHERE latitude IS NULL
        AND numero_voie IS NOT NULL
        AND nom_voie IS NOT NULL
        AND code_postal IS NOT NULL
        LIMIT 500
    """

    rows = await conn.fetch(query)

    if not rows:
        logger.info("Aucune transaction à géocoder")
        return 0

    logger.info(f"Géocodage de {len(rows)} transactions par batches de {batch_size}...")

    geocoded_count = 0

    # Traiter par batches avec rate limiting
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            batch_geocoded = await _geocode_batch(conn, session, batch)
            geocoded_count += batch_geocoded

            # Rate limiting entre batches (sauf pour le dernier)
            if i + batch_size < len(rows):
                logger.debug(f"Pause rate limiting {BAN_RATE_LIMIT_DELAY}s...")
                await asyncio.sleep(BAN_RATE_LIMIT_DELAY)

    logger.info(f"✅ Géocodage terminé: {geocoded_count}/{len(rows)} adresses géocodées")
    return geocoded_count


async def _geocode_batch(
    conn: asyncpg.Connection,
    session: aiohttp.ClientSession,
    batch: List[asyncpg.Record]
) -> int:
    """Géocode un batch de transactions et retourne le nombre géocodé."""

    # Construire les requêtes d'adresse en parallèle
    geocode_tasks = []
    for row in batch:
        address = _build_address(row)
        if address:
            geocode_tasks.append(_geocode_address(session, row['id'], address))

    if not geocode_tasks:
        return 0

    # Exécuter les requêtes en parallèle
    results = await asyncio.gather(*geocode_tasks, return_exceptions=True)

    # Préparer les mises à jour en base
    updates = []
    for result in results:
        if isinstance(result, dict) and 'id' in result and result['longitude'] is not None:
            updates.append((result['longitude'], result['latitude'], result['id']))

    # Mettre à jour en base si on a des résultats
    if updates:
        await conn.executemany(
            "UPDATE transactions SET longitude = $1, latitude = $2 WHERE id = $3",
            updates
        )
        logger.debug(f"✅ Géocodé {len(updates)}/{len(batch)} transactions du batch")
        return len(updates)

    return 0


def _build_address(row: asyncpg.Record) -> Optional[str]:
    """Construit une adresse pour l'API BAN."""
    parts = []

    if row['numero_voie']:
        parts.append(str(row['numero_voie']))

    if row['nom_voie']:
        parts.append(row['nom_voie'])

    if row['code_postal']:
        parts.append(str(row['code_postal']))

    if row['commune']:
        parts.append(row['commune'])

    return ' '.join(parts) if parts else None


async def _geocode_address(
    session: aiohttp.ClientSession,
    transaction_id: str,
    address: str
) -> dict:
    """Géocode une adresse via l'API BAN."""

    try:
        url = f"{BAN_API_URL}?q={quote_plus(address)}&limit=1"

        async with session.get(url) as response:
            if response.status != 200:
                logger.debug(f"Erreur API BAN pour {transaction_id}: status {response.status}")
                return {'id': transaction_id, 'longitude': None, 'latitude': None}

            data = await response.json()

            if data.get('features'):
                coords = data['features'][0]['geometry']['coordinates']
                return {
                    'id': transaction_id,
                    'longitude': coords[0],  # longitude en premier dans GeoJSON
                    'latitude': coords[1]
                }

    except Exception as e:
        logger.debug(f"Erreur géocodage transaction {transaction_id}: {e}")

    return {'id': transaction_id, 'longitude': None, 'latitude': None}


# Conserver la fonction legacy pour compatibilité
async def geocode_transactions(conn: asyncpg.Connection, limit: Optional[int] = None) -> None:
    """
    LEGACY: Géocode les transactions sans coordonnées via l'API BAN.
    Utilise la nouvelle fonction geocode_missing.
    """
    logger.warning("geocode_transactions est dépréciée, utiliser geocode_missing")

    if limit:
        # Si une limite est spécifiée, on doit modifier temporairement la requête
        # Pour simplifier, on utilise geocode_missing normalement
        pass

    await geocode_missing(conn, batch_size=BAN_BATCH_SIZE)


async def main(departement: str, geocode: bool = True, limit: Optional[int] = None) -> None:
    """
    Pipeline complet d'import DVF.

    Args:
        departement: Code département (ex: "75")
        geocode: Activer le géocodage BAN
        limit: Limiter le nombre de lignes à traiter (pour tests)
    """
    start_time = time.time()

    logger.info(f"🚀 Démarrage import DVF département {departement}")

    # Connexion base de données
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='notaire',
        password='notaire_secure_2024',
        database='notaire_app'
    )

    temp_file = None

    try:
        # 1. Téléchargement
        async with aiohttp.ClientSession() as session:
            temp_file = await download_dvf(departement, session)

        # 2. Lecture et normalisation
        with gzip.open(temp_file, 'rt', encoding='utf-8') as f:
            df = pd.read_csv(f, low_memory=False)

            if limit:
                df = df.head(limit)
                logger.info(f"Limite appliquée: traitement de {len(df)} lignes")

        df_clean = normalize_dvf(df)

        if len(df_clean) == 0:
            logger.warning("Aucune transaction valide après filtres")
            return

        # 3. Chargement en base avec déduplication
        inserted_count = await load_to_postgres(df_clean, departement, conn)

        # 4. Géocodage (optionnel)
        if geocode:
            geocoded_count = await geocode_missing(conn, batch_size=50)
            logger.info(f"Géocodage: {geocoded_count} adresses traitées")

        elapsed = time.time() - start_time
        logger.info(f"✅ Import DVF {departement} terminé en {elapsed:.1f}s - "
                   f"{inserted_count} nouvelles transactions")

    except Exception as e:
        logger.error(f"❌ Échec import DVF {departement}: {e}")
        raise

    finally:
        await conn.close()

        # Nettoyage fichier temporaire
        if temp_file and temp_file.exists():
            temp_file.unlink()
            logger.debug(f"Fichier temporaire supprimé: {temp_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import DVF pour estimation immobilière")
    parser.add_argument("--dept", required=True, help="Code département (ex: 75)")
    parser.add_argument("--no-geocode", action="store_true", help="Désactiver le géocodage BAN")
    parser.add_argument("--limit", type=int, help="Limiter le nombre de lignes (tests)")

    args = parser.parse_args()

    asyncio.run(main(
        departement=args.dept,
        geocode=not args.no_geocode,
        limit=args.limit
    ))