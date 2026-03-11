---
name: dvf-pipeline
description: Expertise sur l'import, la normalisation et l'exploitation des données DVF (Demandes de Valeurs Foncières) open data. Active cette skill pour tout ce qui concerne l'import de données immobilières, le pipeline data-pipeline, les transactions DVF, l'estimation de prix, le geocodage BAN, les requêtes analytiques sur les prix immobiliers, ou quand l'utilisateur travaille dans packages/data-pipeline/. Utilise aussi pour les requêtes SQL sur la table transactions ou la vue estimation_stats.
disable-model-invocation: false
allowed-tools: Bash, Read, Write
---

# DVF Pipeline — Guide d'implémentation

## Architecture du pipeline

```
URL data.gouv.fr
    ↓ download_dvf(dept)
fichier .csv.gz
    ↓ normalize_dvf()
DataFrame pandas nettoyé
    ↓ load_to_postgres() via COPY
table transactions (PostgreSQL)
    ↓ geocode_transactions()
coordonnées lat/lon via BAN API
    ↓
vue estimation_stats
```

## Script d'import : `packages/data-pipeline/src/import_dvf.py`

### Colonnes conservées après normalisation
```python
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
}
```

### Filtres qualité appliqués
- nature_mutation == "Vente" uniquement
- type_bien IN ('Appartement', 'Maison', 'Local industriel...')
- prix_vente > 0 et non null
- surface_m2 > 5 et non null
- prix_m2 entre 100 et 50 000 (filtre aberrants)

## Bulk insert PostgreSQL (performance)

```python
# Utiliser COPY via asyncpg, PAS INSERT ligne par ligne
async def load_to_postgres(df: pd.DataFrame, conn):
    records = df.to_records(index=False).tolist()
    await conn.copy_records_to_table(
        'transactions',
        records=records,
        columns=list(df.columns)
    )
```

## API BAN (géocodage)

```
GET https://api-adresse.data.gouv.fr/search/
  ?q=8+bd+du+Port+75001+Paris
  &limit=1

→ { features: [{ geometry: { coordinates: [lon, lat] } }] }
```

### Règle : traiter par batch de 50 adresses max, pause 0.5s entre batches

## Vue SQL estimation_stats

```sql
SELECT code_postal, type_bien,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS prix_m2_median,
       COUNT(*) as nb_transactions
FROM transactions
WHERE date_vente >= NOW() - INTERVAL '24 months'
GROUP BY code_postal, type_bien;
```

## Commandes utiles

```bash
# Import département
python packages/data-pipeline/src/import_dvf.py --dept 75

# Vérifier l'import
docker exec notaire-postgres psql -U notaire -d notaire_app \
  -c "SELECT departement, COUNT(*) FROM transactions GROUP BY 1;"
```
