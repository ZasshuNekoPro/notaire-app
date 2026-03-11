# 🚀 Guide de démarrage Claude Code — Notaire App

## Avant de lancer Claude Code

```bash
# 1. Démarrer l'infrastructure
./scripts/setup.sh

# 2. Vérifier que tout tourne
docker compose ps

# 3. Lancer Claude Code
claude
```

---

## Premier prompt à copier-coller EXACTEMENT

```
/demarrage-projet
```

Ce command va :
- Lire CLAUDE.md et docs/architecture.md
- Vérifier l'état de la BDD et des services
- Afficher ce qui est fait / en cours / à faire
- Te donner la prochaine action recommandée

---

## Prompts par phase (après /demarrage-projet)

### Phase 1 — Auth & Utilisateurs
```
ultrathink

Charge les skills auth-securite et fastapi-conventions.
Implémente le module auth complet dans packages/api/src/ :

1. Génère d'abord les tests dans packages/api/tests/test_auth.py
   couvrant : register, login, refresh, logout, 2FA setup/verify,
   verrouillage après 5 tentatives.

2. Implémente dans cet ordre :
   models/auth.py → schemas/auth.py → services/auth_service.py
   → middleware/auth_middleware.py → routers/auth.py

Respecte strictement les conventions de packages/api/CLAUDE.md.
Fais passer tous les tests avant de passer à l'étape suivante.
```

### Phase 2 — Estimation DVF
```
/phase-estimation
```

### Phase 3 — RAG Juridique
```
/phase-rag
```

### Phase 4 — Succession IA
```
/phase-succession
```

### Fin de session
```
/commit-session
```

---

## Règles à mémoriser

| Situation | Action |
|-----------|--------|
| Début de session | `/demarrage-projet` en premier |
| Contexte à 50% | `/compact` immédiatement |
| Tâche complexe | Ajouter `ultrathink` au début du prompt |
| Changer de module | `/clear` puis recharger le contexte |
| Fin de session | `/commit-session` |
| Bug difficile | Fournir screenshot + logs |

---

## Comptes de test (après seed_dev.py)

| Rôle | Email | Mot de passe |
|------|-------|--------------|
| Admin | admin@test.fr | Admin123! |
| Notaire | notaire1@test.fr | Notaire123! |
| Clerc | clerc@test.fr | Clerc123! |
| Client | client@test.fr | Client123! |
