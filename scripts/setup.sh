#!/bin/bash
# NOTAIRE APP — Démarrage des services
# Usage : ./scripts/setup.sh [--ollama] [--dev]

set -e
BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

USE_OLLAMA=false; DEV_MODE=false
for arg in "$@"; do
  case $arg in --ollama) USE_OLLAMA=true ;; --dev) DEV_MODE=true ;; esac
done

echo -e "\n🏛️  ${BLUE}NOTAIRE APP — Démarrage${NC}\n"

command -v docker >/dev/null 2>&1 || err "Docker non installé"
docker compose version >/dev/null 2>&1 || err "Docker Compose v2 requis"

[ ! -f ".env" ] && { cp config/.env.example .env; warn "Fichier .env créé — configurez vos clés API"; read -p "Appuyez sur Entrée après avoir configuré .env..."; }

mkdir -p data/dvf data/documents

PROFILES=""
$USE_OLLAMA && PROFILES="--profile ollama"
$DEV_MODE   && PROFILES="$PROFILES --profile dev"

log "Démarrage des services Docker..."
docker compose $PROFILES up -d

log "Attente de PostgreSQL..."
until docker compose exec postgres pg_isready -U notaire >/dev/null 2>&1; do sleep 1; done
ok "PostgreSQL prêt"

if $USE_OLLAMA; then
  sleep 3
  OLLAMA_MODEL=$(grep "^OLLAMA_MODEL=" .env | cut -d'=' -f2 | tr -d '"' || echo "mistral:7b")
  log "Téléchargement modèle Ollama : $OLLAMA_MODEL"
  docker compose exec ollama ollama pull "$OLLAMA_MODEL"
  docker compose exec ollama ollama pull nomic-embed-text
  ok "Modèles Ollama prêts"
fi

API_PORT=$(grep "^API_PORT=" .env 2>/dev/null | cut -d'=' -f2 || echo "8000")
echo -e "\n${GREEN}✅ Notaire App démarrée !${NC}"
echo "  🌐 Frontend  : http://localhost:3000"
echo "  ⚡ API       : http://localhost:${API_PORT}"
echo "  📖 API Docs  : http://localhost:${API_PORT}/docs"
$DEV_MODE   && echo "  🗄️  Adminer  : http://localhost:8080"
$USE_OLLAMA && echo "  🤖 Ollama    : http://localhost:11434"
echo ""
echo "  Import DVF (Paris) : python packages/data-pipeline/src/import_dvf.py --dept 75"
echo "  Créer admin        : python scripts/create_admin.py --email admin@test.fr --password Admin123!"
