#!/bin/bash
# HOMEPOT service status check.
# Reports whether PostgreSQL, the backend API, the frontend, and Ollama are
# up. Passwordless-safe: it only uses pg_isready + HTTP probes, so it works
# under HOMEPOT_DB_AUTH=trust (no sudo, no password) and peer/password alike.
#
# Usage: ./scripts/status.sh

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

DB_HOST="${HOMEPOT_DB_HOST:-localhost}"
API_URL="${HOMEPOT_API_URL:-http://localhost:8000/health}"
WEB_URL="${HOMEPOT_WEB_URL:-http://localhost:5173}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434/api/tags}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "HOMEPOT Service Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

check() {
    local name="$1"
    local ok="$2"
    local detail="$3"
    if [ "$ok" = "1" ]; then
        echo -e "  ${GREEN}[UP]${NC}   $name $detail"
    else
        echo -e "  ${RED}[DOWN]${NC} $name $detail"
    fi
}

# 1. PostgreSQL
if pg_isready -h "$DB_HOST" -q 2>/dev/null; then
    PG_UP=1
    PG_DETAIL="(accepting connections on $DB_HOST)"
else
    PG_UP=0
    PG_DETAIL="(not accepting connections — ask server team: sudo systemctl start postgresql)"
fi
check "PostgreSQL" "$PG_UP" "$PG_DETAIL"

# 2. Backend API
if curl -fsS -m 5 "$API_URL" >/dev/null 2>&1; then
    API_UP=1
    API_DETAIL="(healthy at $API_URL)"
else
    API_UP=0
    API_DETAIL="(no response at $API_URL — start with ./scripts/start-dashboard.sh)"
fi
check "Backend API" "$API_UP" "$API_DETAIL"

# 3. Frontend
if curl -fsS -m 5 "$WEB_URL" >/dev/null 2>&1; then
    WEB_UP=1
    WEB_DETAIL="(serving at $WEB_URL)"
else
    WEB_UP=0
    WEB_DETAIL="(no response at $WEB_URL — start with ./scripts/start-dashboard.sh)"
fi
check "Frontend" "$WEB_UP" "$WEB_DETAIL"

# 4. Ollama
if curl -fsS -m 5 "$OLLAMA_URL" >/dev/null 2>&1; then
    OLLAMA_UP=1
    OLLAMA_DETAIL="(responding at $OLLAMA_URL)"
else
    OLLAMA_UP=0
    OLLAMA_DETAIL="(no response at $OLLAMA_URL — start with ./scripts/setup-ollama.sh)"
fi
check "Ollama" "$OLLAMA_UP" "$OLLAMA_DETAIL"

echo ""
if [ "$PG_UP" = "1" ] && [ "$API_UP" = "1" ] && [ "$WEB_UP" = "1" ] && [ "$OLLAMA_UP" = "1" ]; then
    echo -e "${GREEN}All HOMEPOT services are up.${NC}"
elif [ "$PG_UP" = "1" ] && [ "$API_UP" = "1" ]; then
    echo -e "${YELLOW}Backend + database are up; frontend and/or Ollama are not.${NC}"
else
    echo -e "${RED}Some HOMEPOT services are down. See the details above.${NC}"
fi
