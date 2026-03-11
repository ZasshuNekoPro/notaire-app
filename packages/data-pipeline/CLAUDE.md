# Data Pipeline — Import et Normalisation

## Sources
- DVF : https://files.data.gouv.fr/geo-dvf/latest/csv/{dept}.csv.gz
- BAN : https://api-adresse.data.gouv.fr/search/
- Légifrance : https://api.piste.gouv.fr (OAuth2)
- BOFIP : scraping structuré

## Règles performance
- Toujours COPY (asyncpg) pour les bulk inserts
- Batches de 50 pour le géocodage BAN (rate limit)
- Format intermédiaire : Parquet (10x plus compact que CSV)
- Mettre à jour pipeline_runs à chaque run

## Scripts
- `import_dvf.py --dept XX` → import département
- `ingest_legal.py --source legifrance|bofip|all` → RAG
- `scripts/dvf-pipeline/check_import.sh` → vérification

## Filtres qualité DVF
- nature_mutation == "Vente" uniquement
- prix_vente > 0, surface_m2 > 5
- prix_m2 entre 100 et 50 000 €/m²
