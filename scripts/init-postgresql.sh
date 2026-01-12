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
DB_PASSWORD="homepot_dev_password"
DB_HOST="localhost"
DB_PORT="5432"

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo -e "${RED}Error: PostgreSQL is not installed.${NC}"
    echo "Please install PostgreSQL first:"
    echo "  Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib"
    echo "  macOS: brew install postgresql@16"
    exit 1
fi

# Check if PostgreSQL service is running
if ! sudo systemctl is-active --quiet postgresql 2>/dev/null && ! pg_isready -q 2>/dev/null; then
    echo -e "${YELLOW}PostgreSQL service is not running. Starting it...${NC}"
    sudo systemctl start postgresql || {
        echo -e "${RED}Failed to start PostgreSQL service${NC}"
        exit 1
    }
fi

echo -e "${GREEN}PostgreSQL is installed and running${NC}"
echo ""

# Check if database exists
DB_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")

if [ "$DB_EXISTS" = "1" ]; then
    echo -e "${YELLOW}Warning: Database '$DB_NAME' already exists${NC}"
    echo ""
    read -p "Do you want to drop and recreate it? [y/N] " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Dropping existing database..."
        
        # Terminate existing connections
        sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();" || true
        
        # Drop database
        sudo -u postgres psql -c "DROP DATABASE IF EXISTS $DB_NAME;"
        echo -e "${GREEN}Database dropped${NC}"
    else
        echo "Aborted. Database not modified."
        exit 0
    fi
fi

echo ""
echo "Creating PostgreSQL database and user..."

# Create user if it doesn't exist
USER_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'")
if [ "$USER_EXISTS" != "1" ]; then
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
    echo -e "${GREEN}User '$DB_USER' created${NC}"
else
    echo -e "${YELLOW}! User '$DB_USER' already exists${NC}"
fi

# Create database
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
echo -e "${GREEN}Database '$DB_NAME' created${NC}"

# Grant privileges
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
echo -e "${GREEN}Privileges granted${NC}"

# PostgreSQL 15+ requires additional schema permissions
export PGPASSWORD="$DB_PASSWORD"
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "GRANT ALL ON SCHEMA public TO $DB_USER;" 2>/dev/null || true

# Enable TimescaleDB extension if available
sudo -u postgres psql -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;" 2>/dev/null && \
    echo -e "${GREEN}TimescaleDB extension enabled${NC}" || \
    echo -e "${YELLOW}! TimescaleDB not available (using standard PostgreSQL)${NC}"

# Create .env file if it doesn't exist
if [ ! -f "backend/.env" ]; then
    echo "Creating backend/.env from example..."
    if [ -f "backend/.env.example" ]; then
        cp backend/.env.example backend/.env
        # Update connection string in .env
        if [[ "$(uname)" == "Darwin" ]]; then
            # macOS sed requires empty string for -i backup
            sed -i '' "s|DATABASE__URL=.*|DATABASE__URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}|" backend/.env
        else
            # Linux sed
            sed -i "s|DATABASE__URL=.*|DATABASE__URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}|" backend/.env
        fi
        echo -e "${GREEN}Created backend/.env with correct database credentials${NC}"
    else
        echo -e "${YELLOW}! backend/.env.example not found, skipping .env creation${NC}"
    fi
else
    echo -e "${YELLOW}backend/.env already exists, skipping creation${NC}"
fi

echo ""

# Setup .pgpass for convenient access
if [ -f "./scripts/setup-pgpass.sh" ]; then
    ./scripts/setup-pgpass.sh
fi

echo "Initializing database schema and seed data..."

# Determine Python executable
if [ -f ".venv/bin/python3" ]; then
    PYTHON_CMD=".venv/bin/python3"
elif [ -f "backend/.venv/bin/python3" ]; then
    PYTHON_CMD="backend/.venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

# Run Python script to initialize database
$PYTHON_CMD backend/utils/seed_data.py

# Check if initialization succeeded
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}PostgreSQL Database initialization complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Connection details:"
    echo "  Host: $DB_HOST"
    echo "  Port: $DB_PORT"
    echo "  Database: $DB_NAME"
    echo "  User: $DB_USER"
    echo ""
    echo "Connection string (add to backend/.env):"
    echo "  DATABASE__URL=postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
    echo ""
else
    echo ""
    echo -e "${RED}Error: Database initialization failed${NC}"
    exit 1
fi
