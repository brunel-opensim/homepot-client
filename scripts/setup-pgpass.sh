#!/bin/bash
# Setup .pgpass file for PostgreSQL password-free access
# This creates a .pgpass file in your home directory with HOMEPOT database credentials

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "HOMEPOT PostgreSQL .pgpass Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Database credentials
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="homepot_db"
DB_USER="homepot_user"
DB_PASSWORD="homepot_dev_password"

PGPASS_FILE="$HOME/.pgpass"
PGPASS_ENTRY="${DB_HOST}:${DB_PORT}:${DB_NAME}:${DB_USER}:${DB_PASSWORD}"

# Check if .pgpass already exists
if [ -f "$PGPASS_FILE" ]; then
    echo -e "${YELLOW}[INFO]${NC} .pgpass file already exists at: $PGPASS_FILE"
    
    # Check if HOMEPOT entry already exists
    if grep -q "^${DB_HOST}:${DB_PORT}:${DB_NAME}:${DB_USER}:" "$PGPASS_FILE"; then
        echo -e "${YELLOW}[INFO]${NC} HOMEPOT database entry already exists in .pgpass"
        echo ""
        echo "Current entry:"
        grep "^${DB_HOST}:${DB_PORT}:${DB_NAME}:${DB_USER}:" "$PGPASS_FILE"
        echo ""
        read -p "Do you want to update it? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${GREEN}[OK]${NC} Keeping existing entry. No changes made."
            exit 0
        fi
        
        # Remove old entry
        sed -i "/^${DB_HOST}:${DB_PORT}:${DB_NAME}:${DB_USER}:/d" "$PGPASS_FILE"
        echo -e "${GREEN}[OK]${NC} Removed old entry"
    fi
else
    echo -e "${YELLOW}[INFO]${NC} Creating new .pgpass file at: $PGPASS_FILE"
fi

# Add HOMEPOT entry
echo "$PGPASS_ENTRY" >> "$PGPASS_FILE"
echo -e "${GREEN}[OK]${NC} Added HOMEPOT database entry to .pgpass"

# Set correct permissions (required by PostgreSQL)
chmod 600 "$PGPASS_FILE"
echo -e "${GREEN}[OK]${NC} Set permissions to 600 (owner read/write only)"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "You can now run psql commands without password prompts:"
echo ""
echo "  psql -h localhost -U homepot_user -d homepot_db"
echo "  ./scripts/query-db.sh count"
echo ""
echo -e "${YELLOW}Note:${NC} The password is stored in: $PGPASS_FILE"
echo -e "${YELLOW}Security:${NC} This file is only readable by you (chmod 600)"
echo ""
echo "To remove the entry later:"
echo "  sed -i '/homepot_db/d' ~/.pgpass"
echo ""
