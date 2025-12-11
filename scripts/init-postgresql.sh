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

echo -e "${GREEN}✓ PostgreSQL is installed and running${NC}"
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
        echo -e "${GREEN}✓ Database dropped${NC}"
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
    echo -e "${GREEN}✓ User '$DB_USER' created${NC}"
else
    echo -e "${YELLOW}! User '$DB_USER' already exists${NC}"
fi

# Create database
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
echo -e "${GREEN}✓ Database '$DB_NAME' created${NC}"

# Grant privileges
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
echo -e "${GREEN}✓ Privileges granted${NC}"

# PostgreSQL 15+ requires additional schema permissions
export PGPASSWORD="$DB_PASSWORD"
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "GRANT ALL ON SCHEMA public TO $DB_USER;" 2>/dev/null || true

# Enable TimescaleDB extension if available
sudo -u postgres psql -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;" 2>/dev/null && \
    echo -e "${GREEN}✓ TimescaleDB extension enabled${NC}" || \
    echo -e "${YELLOW}! TimescaleDB not available (using standard PostgreSQL)${NC}"

echo ""
echo "Initializing database schema and seed data..."

# Run Python script to initialize database
python3 << 'EOF'
import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path.cwd() / "backend" / "src"))

from homepot.database import DatabaseService
from homepot.models import DeviceType, Device, Job, JobStatus, JobPriority, HealthCheck, AuditLog
from homepot.app.models.UserModel import User, Base as AppBase
from homepot.app.models import AnalyticsModel  # Import module to register models
from passlib.context import CryptContext
from datetime import datetime
from sqlalchemy import select

async def init_database():
    """Initialize PostgreSQL database with schema and seed data."""
    
    print("✓ Importing database service...")
    
    # Create database service (will use DATABASE__URL from .env)
    db_service = DatabaseService()
    
    print("✓ Creating database schema...")
    await db_service.initialize()
    
    # Create analytics tables (uses same Base as User models)
    print("✓ Creating analytics tables...")
    async with db_service.engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.create_all)
    
    print("✓ Database schema created")
    
    # Create test user for analytics validation
    print("✓ Creating test user...")
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    async with db_service.get_session() as session:
        test_user = User(
            email="analytics-test@example.com",
            username="analyticstest",
            hashed_password=pwd_context.hash("testpass123"),
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(test_user)
        await session.commit()
    
    print("✓ Test user created")
    
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
        
        site3 = await db_service.create_site(
            site_id="site-003",
            name="East Side Mall",
            description="Shopping mall location with 4 POS terminals",
            location="789 East Blvd, Mall District"
        )
        print(f"✓ Created demo site: {site3.name}")
        
        # Create demo devices for site 1
        for i in range(1, 6):
            device = await db_service.create_device(
                device_id=f"pos-terminal-{i:03d}",
                name=f"POS Terminal {i}",
                device_type=DeviceType.POS_TERMINAL,
                site_id=site1.site_id,
                ip_address=f"192.168.1.{10+i}",
                config={"gateway_url": "https://payments.example.com"}
            )
            print(f"✓ Created device: {device.name} at {site1.name}")
        
        # Create demo devices for site 2
        for i in range(6, 9):
            device = await db_service.create_device(
                device_id=f"pos-terminal-{i:03d}",
                name=f"POS Terminal {i}",
                device_type=DeviceType.POS_TERMINAL,
                site_id=site2.site_id,
                ip_address=f"192.168.2.{i}",
                config={"gateway_url": "https://payments.example.com"}
            )
            print(f"✓ Created device: {device.name} at {site2.name}")
        
        # Create demo devices for site 3
        devices = []
        for i in range(9, 13):
            device = await db_service.create_device(
                device_id=f"pos-terminal-{i:03d}",
                name=f"POS Terminal {i}",
                device_type=DeviceType.POS_TERMINAL,
                site_id=site3.site_id,
                ip_address=f"192.168.3.{i-8}",
                config={"gateway_url": "https://payments.example.com"}
            )
            devices.append(device)
            print(f"✓ Created device: {device.name} at {site3.name}")
        
        # Get first device for sample data
        async with db_service.get_session() as session:
            result = await session.execute(select(Device).limit(1))
            first_device = result.scalar_one()
            
            # Create sample job
            sample_job = Job(
                job_id="job-sample-001",
                action="Update POS payment config",
                description="Sample job for schema validation",
                priority=JobPriority.NORMAL,
                status=JobStatus.COMPLETED,
                site_id=site1.id,
                device_id=first_device.id,
                payload={"config_version": "1.0.0"},
                created_by=test_user.id,
                completed_at=datetime.utcnow()
            )
            session.add(sample_job)
            await session.commit()
            await session.refresh(sample_job)
            print("✓ Created sample job")
            
            # Create sample health check (provide id explicitly for composite PK)
            sample_health = HealthCheck(
                id=1,
                device_id=first_device.id,
                is_healthy=True,
                response_time_ms=45,
                status_code=200,
                endpoint="/health",
                timestamp=datetime.utcnow()
            )
            session.add(sample_health)
            await session.commit()
            print("✓ Created sample health check")
            
            # Create sample audit log
            sample_audit = AuditLog(
                event_type="job_created",
                description=f"Job {sample_job.job_id} created for site {site1.site_id}",
                user_id=test_user.id,
                job_id=sample_job.id,
                device_id=first_device.id,
                site_id=site1.id,
                event_metadata={"action": "Update POS payment config"}
            )
            session.add(sample_audit)
            await session.commit()
            print("✓ Created sample audit log")
            
            # Create sample analytics records
            from homepot.app.models.AnalyticsModel import (
                APIRequestLog, UserActivity, DeviceStateHistory, 
                JobOutcome, ErrorLog
            )
            
            # Sample API request log
            sample_api_log = APIRequestLog(
                endpoint="/api/v1/sites/site-001/jobs",
                method="POST",
                status_code=200,
                response_time_ms=125.5,
                user_id=str(test_user.id),
                ip_address="192.168.1.100",
                user_agent="HOMEPOT-Client/1.0"
            )
            session.add(sample_api_log)
            print("✓ Created sample API request log")
            
            # Sample user activity
            sample_activity = UserActivity(
                user_id=str(test_user.id),
                activity_type="page_view",
                page_url="/dashboard/sites/site-001",
                duration_ms=3500,
                extra_data={"action": "viewed_job_list"}
            )
            session.add(sample_activity)
            print("✓ Created sample user activity")
            
            # Sample device state history
            sample_state = DeviceStateHistory(
                device_id=first_device.device_id,
                previous_state="offline",
                new_state="online",
                changed_by="system",
                reason="Device came online after reboot"
            )
            session.add(sample_state)
            print("✓ Created sample device state history")
            
            # Sample job outcome
            sample_outcome = JobOutcome(
                job_id=sample_job.job_id,
                job_type="config_update",
                device_id=first_device.device_id,
                status="success",
                duration_ms=2340,
                initiated_by=str(test_user.id),
                extra_data={"config_applied": True, "restart_required": False}
            )
            session.add(sample_outcome)
            print("✓ Created sample job outcome")
            
            # Sample error log
            sample_error = ErrorLog(
                category="validation",
                severity="warning",
                error_code="VAL001",
                error_message="Invalid configuration parameter detected",
                stack_trace="Traceback (most recent call last):\n  File example.py line 42",
                endpoint="/api/v1/config/validate",
                user_id=str(test_user.id),
                context={"param": "invalid_value", "expected": "integer"}
            )
            session.add(sample_error)
            await session.commit()
            print("✓ Created sample error log")
        
        print("")
        print("✓ Database initialized successfully!")
        print("")
        print("Database: PostgreSQL")
        print(f"Host: localhost:5432")
        print(f"Database: homepot_db")
        print(f"Sites created: 3")
        print(f"Devices created: 12")
        print(f"Sample records created in all 11 tables")
        
    except Exception as e:
        print(f"Error creating seed data: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    await db_service.close()

# Run initialization
asyncio.run(init_database())
EOF

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
