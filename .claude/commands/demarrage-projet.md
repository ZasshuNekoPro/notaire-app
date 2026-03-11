---
name: demarrage-projet
description: Workflow de démarrage d'une nouvelle session Claude Code sur le projet notaire-app. Charge tout le contexte nécessaire et affiche l'état du projet. Invoquer avec /demarrage-projet en début de chaque session.
disable-model-invocation: true
---

# /demarrage-projet — Initialisation de session

## Étape 1 : Lecture du contexte global
Lis dans cet ordre :
1. `CLAUDE.md` (vision globale)
2. `docs/architecture.md` (décisions techniques)
3. `docs/roadmap.md` (état d'avancement)

## Étape 2 : État de l'infrastructure
```bash
docker compose ps
```

## Étape 3 : État de la base de données
```bash
docker exec notaire-postgres psql -U notaire -d notaire_app -c "
SELECT
  'users' as table_name, COUNT(*) FROM users
UNION ALL SELECT 'transactions', COUNT(*) FROM transactions
UNION ALL SELECT 'dossiers', COUNT(*) FROM dossiers
UNION ALL SELECT 'knowledge_chunks', COUNT(*) FROM knowledge_chunks
UNION ALL SELECT 'alertes', COUNT(*) FROM alertes;"
```

## Étape 4 : Résumé et prochaine action
Affiche :
- ✅ Ce qui est implémenté (tables non vides, services existants)
- 🔄 Ce qui est en cours
- 📋 Prochaine étape recommandée selon la roadmap

## Étape 5 : Rappel des règles critiques
- Une session = un module maximum
- Tests avant implémentation
- /compact à 50% de contexte
- Documenter les décisions dans docs/architecture.md
