#!/bin/bash
# PostgreSQL Database Initialization Script for HOMEPOT Client
# This script creates a fresh PostgreSQL database with proper schema and seed data
# Usage: ./scripts/init-postgresql.sh

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "HOMEPOT PostgreSQL Database Initialization"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Database connection details
DB_NAME="homepot_db"
DB_USER="homepot_user"
DB_HOST="localhost"
DB_PORT="5432"

# Authentication mode for database administration.
#   HOMEPOT_DB_AUTH=peer     (DEFAULT) macOS/Homebrew admin + sudo -u postgres on
#                            Linux. Password auth, .pgpass helper used.
#   HOMEPOT_DB_AUTH=trust    Passwordless local dev. Server team has configured
#                            `trust` in pg_hba.conf; demouser needs NO sudo and NO
#                            password. .pgpass/PGPASSWORD are skipped, the connect
#                            URL omits the password entirely.
#   HOMEPOT_DB_AUTH=password Explicit password auth (hardened servers).
DB_AUTH="${HOMEPOT_DB_AUTH:-peer}"
DB_PASSWORD="${HOMEPOT_DB_PASSWORD:-homepot_dev_password}"

# Validate auth mode
case "$DB_AUTH" in
    peer|trust|password) ;;
    *) echo -e "${RED}Error: HOMEPOT_DB_AUTH must be one of: peer, trust, password (got '$DB_AUTH')${NC}" >&2; exit 1 ;;
esac

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo -e "${RED}Error: PostgreSQL is not installed.${NC}"
    echo "Please install PostgreSQL first:"
    echo "  Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib"
    echo "  macOS: brew install postgresql@16"
    exit 1
fi

# Check if PostgreSQL service is running
start_postgres() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if ! pg_isready -q; then
             echo -e "${YELLOW}PostgreSQL service is not running. Starting via Homebrew...${NC}"
             brew services start postgresql || brew services start postgresql@14 || brew services start postgresql@16 || {
                 echo -e "${RED}Failed to start PostgreSQL. Is it installed via Homebrew?${NC}"
                 exit 1
             }
             sleep 3
        fi
    else
        if [ "$DB_AUTH" = "trust" ]; then
            # Passwordless trust: server team keeps the service running; demouser
            # has NO sudo. Only readiness is checked - starting the service is the
            # server team's job (documented in docs/server-deployment.md).
            if ! pg_isready -q 2>/dev/null; then
                echo -e "${RED}Error: PostgreSQL is not accepting connections.${NC}"
                echo "Under HOMEPOT_DB_AUTH=trust, demouser cannot start the service."
                echo "Please ask the server team to: sudo systemctl start postgresql"
                exit 1
            fi
        elif ! sudo systemctl is-active --quiet postgresql 2>/dev/null && ! pg_isready -q 2>/dev/null; then
            echo -e "${YELLOW}PostgreSQL service is not running. Starting it...${NC}"
            sudo systemctl start postgresql || {
                echo -e "${RED}Failed to start PostgreSQL service${NC}"
                exit 1
            }
        fi
    fi
}

start_postgres

echo -e "${GREEN}PostgreSQL is installed and running${NC}"
echo ""

# Determine PSQL command prefix (mode-aware).
if [ "$DB_AUTH" = "trust" ]; then
    # Passwordless trust: demouser needs NO sudo and NO password. The admin
    # identity (superuser) differs by OS because Homebrew and Debian/Ubuntu
    # initdb the cluster with different default superusers:
    #   - macOS/Homebrew: the login user is the superuser ("$(whoami)") and
    #     "trust" on 127.0.0.1 is already the Homebrew default, so the Mac
    #     demouser connects as ITS OWN login user — no sudo, no password.
    #   - Linux/Ubuntu: the server team has created the `postgres` superuser
    #     reachable over localhost under trust (docs note: server team ran
    #     `createuser -s postgres`-equivalent ONCE), so the server demouser
    #     connects as `postgres`.
    # REVERT WHEN PRODUCTION READY (trust -> password). The OS split below
    # is a DEV convenience; standardize every env on `postgres` over localhost
    # trust and drop the darwin branch (grep -rn 'REVERT' to find all spots).
    if [ "$DB_AUTH" = "trust" ] && [[ "$OSTYPE" == "darwin"* ]]; then
        PSQL_ADMIN="psql -h localhost -U $(whoami)"
    else
        PSQL_ADMIN="psql -h localhost -U postgres"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # On macOS Homebrew, the login user is the admin
    PSQL_ADMIN="psql postgres"
else
    # On Linux, switches to the postgres superuser
    PSQL_ADMIN="sudo -u postgres psql"
fi

# Check if database exists
DB_EXISTS=$($PSQL_ADMIN -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")

if [ "$DB_EXISTS" = "1" ]; then
    echo -e "${YELLOW}Warning: Database '$DB_NAME' already exists${NC}"
    echo ""
    read -p "Do you want to drop and recreate it? [y/N] " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Dropping existing database..."
        
        # Terminate existing connections
        $PSQL_ADMIN -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();" || true
        
        # Drop database
        $PSQL_ADMIN -c "DROP DATABASE IF EXISTS $DB_NAME;"
        echo -e "${GREEN}Database dropped${NC}"
    else
        echo "Aborted. Database not modified."
        exit 0
    fi
fi

echo ""
echo "Creating PostgreSQL database and user..."

# Create user if it doesn't exist
USER_EXISTS=$($PSQL_ADMIN -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'")
if [ "$USER_EXISTS" != "1" ]; then
    $PSQL_ADMIN -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
    echo -e "${GREEN}User '$DB_USER' created${NC}"
else
    echo -e "${YELLOW}! User '$DB_USER' already exists${NC}"
fi

# Create database
$PSQL_ADMIN -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
echo -e "${GREEN}Database '$DB_NAME' created${NC}"

# Grant privileges
$PSQL_ADMIN -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
echo -e "${GREEN}Privileges granted${NC}"

# PostgreSQL 15+ requires additional schema permissions. Under trust the
# connect omits the password, so skip the PGPASSWORD export (demouser needs
# no password; exporting it would be misleading).
if [ "$DB_AUTH" != "trust" ]; then
    export PGPASSWORD="$DB_PASSWORD"
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "GRANT ALL ON SCHEMA public TO $DB_USER;" 2>/dev/null || true
else
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "GRANT ALL ON SCHEMA public TO $DB_USER;" 2>/dev/null || true
fi

# Enable TimescaleDB extension if available
$PSQL_ADMIN -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;" 2>/dev/null && \
    echo -e "${GREEN}TimescaleDB extension enabled${NC}" || \
    echo -e "${YELLOW}! TimescaleDB not available (using standard PostgreSQL)${NC}"

# Create .env file if it doesn't exist
if [ ! -f "backend/.env" ]; then
    echo "Creating backend/.env from example..."
    if [ -f "backend/.env.example" ]; then
        cp backend/.env.example backend/.env
        # Update connection string in .env. Under trust the password is omitted
        # entirely (there is no password), otherwise it is embedded.
        if [[ "$(uname)" == "Darwin" ]]; then
            # macOS sed requires empty string for -i backup
            if [ "$DB_AUTH" = "trust" ]; then
                sed -i '' "s|DATABASE__URL=.*|DATABASE__URL=postgresql://${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}|" backend/.env
            else
                sed -i '' "s|DATABASE__URL=.*|DATABASE__URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}|" backend/.env
            fi
        else
            # Linux sed
            if [ "$DB_AUTH" = "trust" ]; then
                sed -i "s|DATABASE__URL=.*|DATABASE__URL=postgresql://${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}|" backend/.env
            else
                sed -i "s|DATABASE__URL=.*|DATABASE__URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}|" backend/.env
            fi
        fi
        echo -e "${GREEN}Created backend/.env with correct database credentials${NC}"
    else
        echo -e "${YELLOW}! backend/.env.example not found, skipping .env creation${NC}"
    fi
else
    echo -e "${YELLOW}backend/.env already exists, skipping creation${NC}"
fi

echo ""

# Setup .pgpass for convenient access. Under trust there is no password to
# store, so the helper is skipped entirely (demouser connects passwordless).
if [ "$DB_AUTH" != "trust" ] && [ -f "./scripts/setup-pgpass.sh" ]; then
    ./scripts/setup-pgpass.sh
fi

echo "Initializing database schema and admin user..."

# Determine Python executable
if [ -f ".venv/bin/python3" ]; then
    PYTHON_CMD=".venv/bin/python3"
elif [ -f "backend/.venv/bin/python3" ]; then
    PYTHON_CMD="backend/.venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

# Run Python script to initialize the schema + default admin user only.
# Demo data (tenants, sites, simulated devices, analytics) is opt-in via
# ./scripts/seed-demo-data.sh so a fresh database starts clean.
# Under trust the password is omitted from the URL (there is no password).
if [ "$DB_AUTH" = "trust" ]; then
    seed_url="postgresql://${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
else
    seed_url="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
fi
DATABASE__URL="$seed_url" \
    $PYTHON_CMD backend/utils/seed_data.py --schema-only

# Upgrade alembic migration state so that schema PRs cannot silently break
# existing installs.  This runs after the app's create_all bootstraps the
# base schema, applying any additive migrations from the base to head.
if [ "$DB_AUTH" = "trust" ]; then
    export DATABASE__URL="postgresql://${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
else
    export DATABASE__URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
fi
bash scripts/upgrade-db.sh

# Check if initialization succeeded
