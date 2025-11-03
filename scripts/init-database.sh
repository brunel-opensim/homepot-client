#!/bin/bash
# Database Initialization Script for HOMEPOT Client
# This script creates a fresh database with proper schema and seed data
# Usage: ./scripts/init-database.sh

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "HOMEPOT Database Initialization"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

DB_PATH="data/homepot.db"
BACKUP_DIR="data/backups"

# Check if database exists
if [ -f "$DB_PATH" ]; then
    echo -e "${YELLOW}Warning: Database already exists at $DB_PATH${NC}"
    echo ""
    read -p "Do you want to backup and recreate it? [y/N] " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Create backup directory
        mkdir -p "$BACKUP_DIR"
        
        # Create backup with timestamp
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_FILE="$BACKUP_DIR/homepot_backup_$TIMESTAMP.db"
        
        echo "Creating backup: $BACKUP_FILE"
        cp "$DB_PATH" "$BACKUP_FILE"
        echo -e "${GREEN}✓ Backup created${NC}"
        
        # Remove old database
        rm "$DB_PATH"
        echo -e "${GREEN}✓ Old database removed${NC}"
    else
        echo "Aborted. Database not modified."
        exit 0
    fi
fi

echo ""
echo "Creating new database..."

# Ensure data directory exists
mkdir -p data

# Run Python script to initialize database
python3 << 'EOF'
import asyncio
import sys
import os
from pathlib import Path

# Add backend to path (using current directory as we're in project root)
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from homepot.database import DatabaseService
from homepot.models import Base, Site, Device, Job, User, DeviceType, DeviceStatus, JobStatus
from sqlalchemy.ext.asyncio import create_async_engine

async def init_database():
    """Initialize database with schema and seed data."""
    
    # Create database engine
    db_url = "sqlite+aiosqlite:///data/homepot.db"
    engine = create_async_engine(db_url, echo=False)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✓ Database schema created")
    
    # Create seed data
    db_service = DatabaseService()
    
    # Create demo sites
    try:
        site1 = await db_service.create_site(
            site_id="site-001",
            name="Main Store - Downtown",
            description="Primary retail location with 5 POS terminals",
            location="123 Main St, Downtown"
        )
        print(f"✓ Created demo site: {site1.name}")
        
        site2 = await db_service.create_site(
            site_id="site-002", 
            name="West Branch",
            description="Secondary location with 3 POS terminals",
            location="456 West Ave, West Side"
        )
        print(f"✓ Created demo site: {site2.name}")
        
        # Create demo devices for site 1
        for i in range(1, 6):
            device = await db_service.create_device(
                device_id=f"pos-terminal-{i:03d}",
                name=f"POS Terminal {i}",
                device_type=DeviceType.POS_TERMINAL,
                site_id=site1.id,
                ip_address=f"192.168.1.{10+i}",
                config={"gateway_url": "https://payments.example.com"}
            )
            print(f"✓ Created device: {device.name}")
        
        # Create demo devices for site 2
        for i in range(6, 9):
            device = await db_service.create_device(
                device_id=f"pos-terminal-{i:03d}",
                name=f"POS Terminal {i}",
                device_type=DeviceType.POS_TERMINAL,
                site_id=site2.id,
                ip_address=f"192.168.2.{i}",
                config={"gateway_url": "https://payments.example.com"}
            )
            print(f"✓ Created device: {device.name}")
        
        print("")
        print("✓ Database initialized successfully!")
        print("")
        print("Database location: data/homepot.db")
        print(f"Sites created: 2")
        print(f"Devices created: 8")
        
    except Exception as e:
        print(f"Error creating seed data: {e}")
        raise
    
    await engine.dispose()

# Run initialization
asyncio.run(init_database())
EOF

# Check if initialization succeeded
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Database initialization complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
else
    echo ""
    echo "Error: Database initialization failed"
    exit 1
fi
