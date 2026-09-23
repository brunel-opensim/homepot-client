#!/bin/bash
# HOMEPOT database reset (development).
# Drops and recreates the database, then re-applies the base schema via
# init-postgresql.sh so a fresh install is reproduced exactly.
#
# Passwordless-safe: honours HOMEPOT_DB_AUTH just like init-postgresql.sh.
#   HOMEPOT_DB_AUTH=trust   passwordless; demouser needs NO sudo and NO
#                           password. PGPASSWORD is NOT exported.
#   HOMEPOT_DB_AUTH=peer    (default) dev machine - writes .pgpass-like creds.
#
# Usage: ./scripts/reset-db.sh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Database connection details (must match init-postgresql.sh)
DB_NAME="homepot_db"
DB_USER="homepot_user"
DB_HOST="localhost"
DB_PORT="5432"
DB_PASSWORD="homepot_dev_password"

# Authentication mode (mirrors init-postgresql.sh) - read from env so deploy
# scripts and the deployment doc drive the same value.
DB_AUTH="${HOMEPOT_DB_AUTH:-peer}"

case "$DB_AUTH" in
    peer|trust|password) ;;
    *) echo -e "${RED}Error: HOMEPOT_DB_AUTH must be one of: peer, trust, password (got '$DB_AUTH')${NC}" >&2; exit 1 ;;
esac

# psql admin prefix - trust connects as the OS-aware superuser (passwordless).
# Same OS split as init-postgresql.sh:
#   - macOS/Homebrew: the login user IS the superuser, so trust admin connects
#     as "$(whoami)" (Homebrew default is already trust on 127.0.0.1).
#   - Linux/Ubuntu: the server team created the `postgres` superuser reachable
#     over localhost under trust, so the server demouser connects as `postgres`.
if [ "$DB_AUTH" = "trust" ]; then
    # REVERT WHEN PRODUCTION READY (trust -> password). Same OS split policy
    # as init-postgresql.sh — keep in lockstep, drop darwin branch on revert.
    if [[ "$OSTYPE" == "darwin"* ]]; then
        PSQL_ADMIN="psql -h localhost -U $(whoami)"
    else
        PSQL_ADMIN="psql -h localhost -U postgres"
    fi
elif [[ "$(uname)" == "Darwin" ]]; then
    PSQL_ADMIN="psql postgres"
else
    PSQL_ADMIN="sudo -u postgres psql"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "HOMEPOT Database Reset"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Confirm before destroying data
read -p "Drop database '$DB_NAME' and recreate a fresh one? [y/N] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Aborted. Database not modified.${NC}"
    exit 0
fi
echo ""

# Terminate existing connections to the database
echo "Terminating existing connections..."
$PSQL_ADMIN -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();" 2>/dev/null || true

# Drop and recreate the database, granting ownership to our user
echo "Dropping and recreating database '$DB_NAME'..."
$PSQL_ADMIN -c "DROP DATABASE IF EXISTS $DB_NAME;"
$PSQL_ADMIN -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
echo -e "${GREEN}Database '$DB_NAME' recreated${NC}"

# PostgreSQL 15+ requires schema privileges. Under trust the password is
# omitted (there is none); otherwise PGPASSWORD is set for convenience.
echo "Granting schema privileges..."
if [ "$DB_AUTH" != "trust" ]; then
    export PGPASSWORD="$DB_PASSWORD"
fi
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;" 2>/dev/null || true

echo ""

# Re-initialize the base schema + admin user (same script the init flow uses,
# so reset and fresh-install always agree). init-postgresql.sh detects the
# .env already exists and only runs the schema/seed part - perfect for reset.
echo -e "${YELLOW}Re-running init to reapply base schema and admin user...${NC}"
./scripts/init-postgresql.sh

echo -e "${GREEN}Database reset complete.${NC}"
