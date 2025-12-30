# Getting Started with HOMEPOT

Welcome to **HOMEPOT** (Homogenous Cyber Management of End-Points and OT) - an enterprise-grade POS payment gateway management system for the HOMEPOT consortium.

> **Note**: HOMEPOT uses a monorepo structure with separate `backend/`, `frontend/`, and `ai/` directories. This guide focuses on the backend setup. For detailed information about the structure, see the [Monorepo Migration Guide](monorepo-migration.md) and [Running Locally Guide](running-locally.md).

## Quick Start (5 minutes)

### Prerequisites

- **Python**: 3.9 or higher
- **Git**: Latest version
- **HOMEPOT Consortium Access**: Repository access required

### Installation & Setup

```bash
# 1. Clone the repository
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Navigate to backend directory
cd backend

# 4. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### Database Setup (Required)

> **Important**: The database file is **NOT included in git**. You must create it after cloning.

The database will be empty when you first clone the repository. You need to initialize it with the schema and demo data:

#### **Option 1: Using the initialization script (Recommended)**

```bash
# From project root (not backend/)
cd ..  # Go back to homepot-client/
./scripts/init-postgresql.sh
```

This creates:
- PostgreSQL database `homepot_db` with all tables

### Next Steps

Once you have completed the setup, proceed to the [Accessing Dashboard](accessing-dashboard.md) guide to learn how to start the application and log in.
- **3 demo sites** (Main Store Downtown, West Branch, East Side Mall)  
- **12 demo devices** (POS terminals)

#### **Option 2: Using Python directly**

```bash
# From backend/ directory
python -c "
import asyncio
import sys
sys.path.insert(0, 'src')
from homepot.database import DatabaseService

async def init():
    db = DatabaseService()
    await db.initialize()
    await db.close()

asyncio.run(init())
"
```

#### **What Gets Created**

After initialization, you'll have:
- **Sites table**: 3 demo retail locations
- **Devices table**: 12 POS terminals distributed across sites
- **Jobs table**: Empty (ready for configuration updates)
- **Users table**: Empty (ready for user management)

You can verify the database:
```bash
# From project root
export PGPASSWORD='homepot_dev_password'
psql -h localhost -U homepot_user -d homepot_db -c "SELECT COUNT(*) as sites FROM sites; SELECT COUNT(*) as devices FROM devices;"
# Expected: 3 sites, 12 devices
```

> **PostgreSQL Required:** HOMEPOT now uses PostgreSQL for production-ready performance. See [docs/postgresql-migration-complete.md](postgresql-migration-complete.md) for details.

### Verify Installation

```bash
# 6. Check the version (from backend/ directory)
python -m homepot.cli version

# 7. More information
python -m homepot.cli info

# 8. Test configuration (from root directory)
cd ..  # Return to root
python -m pytest backend/tests/test_client.py -v --disable-warnings
```

### Start the Backend Server

When ready to start the client:

```bash
# Start the backend server (from backend/ directory)
cd backend
python -m uvicorn homepot.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# Start the backend server (from backend/app directory)(After restrcture the backend api main.py file in inside the app dir)
cd backend
python -m uvicorn homepot.app.main:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag enables auto-restart on code changes (development mode).

### Verify Installation

Open a new terminal and test the system:

```bash
# Check system health
curl http://localhost:8000/health | python3 -m json.tool
# Expected: {"status":"healthy","client_connected":true,"version":"0.1.0"}

# View all POS sites
curl http://localhost:8000/sites | python3 -m json.tool
# Expected: Array of 2 demo sites (Main Store Downtown, West Branch)

# View all devices
curl http://localhost:8000/devices | python3 -m json.tool
# Expected: Array of 8 POS terminals
```

Expected output for health check:

```json
{
    "status": "healthy",
    "client_connected": true,
    "version": "0.1.0",
    "timestamp": 2021.463
}
```

### Access the System

- **Dashboard**: [http://localhost:8000](http://localhost:8000) - Real-time POS monitoring
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs) - Interactive API explorer
- **Health**: [http://localhost:8000/health](http://localhost:8000/health) - System status

## What You Have

Congratulations! You now have a complete enterprise POS management system with:

- **3 Demo Sites** (Main Store Downtown, West Branch, East Side Mall)
- **12 POS Devices** (realistic terminal configuration)
- **Real-time Dashboard** (live monitoring with WebSocket updates)
- **Enterprise Audit Logging** (compliance-ready event tracking)
- **Complete REST API** (comprehensive device management)
- **PostgreSQL Database** (production-ready with async performance)

> **Need more data?** You can create additional sites and devices using the REST API at [http://localhost:8000/docs](http://localhost:8000/docs) or modify `scripts/init-postgresql.sh` to add more demo data.

## Next Steps

### For New Users
- **[POS Management Guide](pos-management.md)** - Manage sites, devices, and jobs
- **[Dashboard Guide](real-time-dashboard.md)** - Real-time monitoring and WebSocket features

### For Developers
- **[Agent Simulation Guide](agent-simulation.md)** - POS terminal simulation and management
- **[Development Guide](development-guide.md)** - Testing, code quality, and contributing

### For Operators
- **[Audit & Compliance Guide](audit-compliance.md)** - Enterprise logging and reporting
- **[Deployment Guide](deployment-guide.md)** - Production deployment with Docker

## Troubleshooting

### Common Issues

**Database Connection Error:**
```bash
# If you get "database connection" errors:
# 1. Ensure PostgreSQL is running:
sudo systemctl status postgresql

# 2. Check database exists:
export PGPASSWORD='homepot_dev_password'
psql -h localhost -U homepot_user -d homepot_db -c "SELECT 1;"

# 3. If needed, reinitialize:
./scripts/init-postgresql.sh
```

**Database Schema Mismatch (After git pull):**
```bash
# If someone updated the database schema (models.py)
# You need to recreate your database:
./scripts/init-postgresql.sh
# Answer 'y' to drop and recreate
# This will reset all data to demo state
```

**"Address already in use" Error:**
```bash
# Kill process using port 8000
sudo kill $(lsof -ti :8000)

# Restart the server
cd backend
python -m uvicorn homepot.main:app --host 0.0.0.0 --port 8000 --reload
```

**Connection Issues:**
```bash
# Check if server is running (from root directory)
curl http://localhost:8000/health

# If connection refused, restart from backend/ directory
cd backend
python -m uvicorn homepot.main:app --host 0.0.0.0 --port 8000 --reload
```

**Want to Start Fresh?**
```bash
# Drop and recreate PostgreSQL database
./scripts/init-postgresql.sh
# You'll get clean demo data (3 sites, 12 devices)
```

### Getting Help

- **[GitHub Issues](https://github.com/brunel-opensim/homepot-client/issues)** - Bug reports and feature requests
- **[Collaboration Guide](collaboration-guide.md)** - Development and contribution guidelines
- **[Development Guide](development-guide.md)** - Testing and code quality
- **[PostgreSQL Migration](postgresql-migration-complete.md)** - Database architecture details

---

*Ready to explore? Start with the [POS Management Guide](pos-management.md) to learn how to manage your POS ecosystem.*
