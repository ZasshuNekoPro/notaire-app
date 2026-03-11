---
name: commit-session
description: Finalise une session de développement. Documente les décisions, met à jour la roadmap, puis commit le travail. Invoquer avec /commit-session en fin de session.
disable-model-invocation: true
---

# /commit-session — Finalisation de session

## Étape 1 — Documentation des décisions
Mets à jour `docs/architecture.md` avec :
- Les nouvelles décisions techniques prises dans cette session
- Les ADR (Architecture Decision Records) correspondants

## Étape 2 — Mise à jour de la roadmap
Coche les tâches complétées dans `docs/roadmap.md`.
Ajoute les nouvelles tâches découvertes.

## Étape 3 — Tests finaux
```bash
pytest packages/ -v --tb=short 2>&1 | tail -20
```

## Étape 4 — Vérification de l'app
```bash
curl http://localhost:8000/health
docker compose ps
```

## Étape 5 — Commit Git
```bash
git add -A
git status
```
Propose un message de commit en suivant ce format :
`feat(module): description concise de ce qui a été implémenté`

Puis commite :
```bash
git commit -m "feat(MODULE): DESCRIPTION"
```

## Étape 6 — Résumé pour la prochaine session
Affiche :
- Ce qui a été fait dans cette session
- Les fichiers modifiés/créés
- La prochaine étape recommandée
