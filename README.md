# 🏛️ Notaire App

Assistant IA pour notaires : estimation immobilière, rédaction d'actes, succession automatique.

## Démarrage rapide

```bash
# 1. Configuration
cp config/.env.example .env
# Éditer .env : choisir AI_PROVIDER + clé API

# 2. Lancer l'application
./scripts/setup.sh

# 3. Créer le compte admin
python scripts/create_admin.py --email admin@etude.fr --password MonMotDePasse123

# 4. Insérer les données de test
python scripts/seed_dev.py

# 5. Importer données DVF (Paris)
python packages/data-pipeline/src/import_dvf.py --dept 75

# 6. Ouvrir l'application
# http://localhost:3000
```

## Démo chez un notaire

```bash
# Tunnel public Cloudflare (5 minutes)
bash scripts/demo-tunnel.sh
```

## URLs

| Service     | URL                          |
|-------------|------------------------------|
| Application | http://localhost:3000        |
| API         | http://localhost:8000        |
| API Docs    | http://localhost:8000/docs   |

## Providers IA supportés

| Provider    | .env                         | Coût      |
|-------------|------------------------------|-----------|
| Claude      | AI_PROVIDER=anthropic        | Payant    |
| GPT-4o      | AI_PROVIDER=openai           | Payant    |
| Ollama      | AI_PROVIDER=ollama           | Gratuit   |
| LM Studio   | AI_PROVIDER=custom           | Gratuit   |

## Déploiement VPS

```bash
DOMAIN=demo.notaire-app.fr bash scripts/deploy.sh
```
