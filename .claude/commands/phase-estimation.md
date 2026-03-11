---
name: phase-estimation
description: Lance le workflow complet de la Phase 2 — Estimation immobilière DVF. Orchestre l'import des données DVF, la création de l'API d'estimation, et la page de test frontend. Invoquer avec /phase-estimation.
disable-model-invocation: true
---

# /phase-estimation — Workflow Phase 2

Charge le skill `dvf-pipeline` avant de commencer.

## Séquence d'implémentation

### Étape 1 — Amélioration du pipeline DVF
Améliore `packages/data-pipeline/src/import_dvf.py` :
- Ajouter `load_to_postgres()` avec COPY asyncpg
- Ajouter `geocode_transactions()` via API BAN (batch 50)
- Mettre à jour `pipeline_runs` à chaque run

Générer les tests dans `packages/data-pipeline/tests/test_import.py` d'abord.

### Étape 2 — API d'estimation
Créer `packages/api/src/routers/estimations.py` :
- `GET /estimations/stats?code_postal=&type_bien=` (depuis vue estimation_stats, cache Redis 1h)
- `POST /estimations/analyse` (20 comparables DVF + analyse LLM)
- `GET /estimations/carte?dept=` (GeoJSON pour carte)

### Étape 3 — Test d'import
```bash
python packages/data-pipeline/src/import_dvf.py --dept 75
bash .claude/skills/dvf-pipeline/scripts/check_import.sh
```

### Étape 4 — Page de test frontend
Créer `packages/web/src/pages/test-estimation.tsx` :
- Formulaire adresse + type + surface
- Affichage résultat estimation + comparables
- Carte Leaflet avec points DVF

## Critère de succès
```bash
curl http://localhost:8000/estimations/stats?code_postal=75008&type_bien=Appartement
# → Retourne prix médian, nb transactions
```
