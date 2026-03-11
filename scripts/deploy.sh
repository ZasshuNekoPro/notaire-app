#!/bin/bash
# NOTAIRE APP — Déploiement sur VPS Ubuntu
# Usage : DOMAIN=demo.notaire-app.fr bash scripts/deploy.sh

set -e
BLUE='\033[0;34m'; GREEN='\033[0;32m'; NC='\033[0m'
log() { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()  { echo -e "${GREEN}[OK]${NC} $1"; }

DOMAIN=${DOMAIN:-"localhost"}
log "Déploiement pour le domaine : $DOMAIN"

# Docker
command -v docker >/dev/null 2>&1 || { curl -fsSL https://get.docker.com | sh; }
ok "Docker prêt"

# Caddy (reverse proxy HTTPS automatique)
if ! command -v caddy >/dev/null 2>&1; then
  log "Installation de Caddy..."
  apt install -y debian-keyring debian-archive-keyring apt-transport-https curl 2>/dev/null
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
  apt update && apt install caddy -y
fi

# Caddyfile
cat > /etc/caddy/Caddyfile << CADDYEOF
$DOMAIN {
    reverse_proxy /api/* localhost:8000
    reverse_proxy /* localhost:3000
}
CADDYEOF

systemctl reload caddy
ok "Caddy configuré pour $DOMAIN"

# .env de production
[ ! -f ".env" ] && { cp config/.env.example .env; echo "⚠️  Configurez .env avant de continuer"; exit 1; }

# Démarrage
docker compose up -d --build
ok "Application démarrée"

echo ""
echo "✅ Déployé sur https://$DOMAIN"
echo "   Créer admin : python scripts/create_admin.py --email admin@etude.fr --password VotreMotDePasse"
