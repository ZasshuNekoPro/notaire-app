#!/bin/bash
# Script de vérification du pipeline DVF
# Vérifie l'état des imports et la qualité des données

set -euo pipefail

# Configuration
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-notaire}
DB_PASSWORD=${DB_PASSWORD:-notaire_secure_2024}
DB_NAME=${DB_NAME:-notaire_app}

# Couleurs pour l'affichage
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Vérification du pipeline DVF - $(date)"
echo "========================================"

# Fonction de connexion PostgreSQL
run_sql() {
    local query="$1"
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "$query" 2>/dev/null | xargs
}

# 1. Vérification de la connectivité
echo -n "🔌 Connexion base de données... "
if run_sql "SELECT 1;" >/dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}ÉCHEC${NC}"
    echo "❌ Impossible de se connecter à PostgreSQL"
    exit 1
fi

# 2. Statistiques des données
echo ""
echo "📊 Statistiques du pipeline DVF:"
echo "---------------------------------"

# Nombre total de transactions
total_transactions=$(run_sql "SELECT COALESCE(COUNT(*), 0) FROM transactions;")
echo "📈 Total transactions: $(printf '%d' $total_transactions)"

echo ""
echo -e "${GREEN}✅ Vérification terminée${NC}"
