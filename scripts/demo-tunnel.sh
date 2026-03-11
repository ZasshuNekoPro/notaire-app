#!/bin/bash
# NOTAIRE APP — Tunnel public pour démo (Cloudflare)
# Usage : bash scripts/demo-tunnel.sh

set -e
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "\n🌐 Création d'un tunnel public pour la démo...\n"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo -e "${YELLOW}Installation de cloudflared...${NC}"
  if [[ "$OSTYPE" == "darwin"* ]]; then
    brew install cloudflare/cloudflare/cloudflared
  else
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    dpkg -i cloudflared-linux-amd64.deb
  fi
fi

echo -e "${GREEN}✅ L'URL publique apparaît ci-dessous (lien valide tant que ce terminal est ouvert)${NC}"
echo -e "   Partagez ce lien au notaire pour la démo\n"
cloudflared tunnel --url http://localhost:3000
