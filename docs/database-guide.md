# Database Guide

## Overview

The HOMEPOT system uses **PostgreSQL** for production-ready performance and scalability. This guide covers database setup, management, and usage patterns for the POS management system.

> **Migration Note:** HOMEPOT previously supported SQLite but has migrated to PostgreSQL for better async support, improved performance, and production readiness. See [PostgreSQL Migration Guide](postgresql-migration-complete.md) for details.

## Database Structure

### Core Tables

The HOMEPOT database consists of the following main entities:

- **`sites`** - Restaurant locations and chain management
- **`devices`** - POS terminals and hardware inventory
- **`jobs`** - Configuration update and management tasks
- **`health_checks`** - Device monitoring and status tracking
- **`audit_logs`** - System events and compliance tracking
- **`users`** - System users and authentication

### Entity Relationships

```
Sites (1) ←→ (Many) Devices
Sites (1) ←→ (Many) Jobs
Devices (1) ←→ (Many) Health Checks
Jobs (1) ←→ (Many) Audit Logs
```

## Quick Start

### Development Setup

1. **Clone and Navigate**
   ```bash
   git clone <repository>
   cd homepot-client
   ```

2. **Install PostgreSQL**
   ```bash
   # Ubuntu/Debian
   sudo apt install postgresql postgresql-contrib
   
   # macOS
   brew install postgresql@16
   ```

3. **Initialize Database**
   ```bash
   ./scripts/init-postgresql.sh
   ```
   
   This creates:
   - PostgreSQL database `homepot_db`
   - 3 demo sites
   - 12 POS terminals
   - User authentication tables

4. **Test Connection**
   ```bash
   export PGPASSWORD='homepot_dev_password'
   psql -h localhost -U homepot_user -d homepot_db -c "SELECT COUNT(*) FROM sites;"
   ```

## Database Organization

### File Structure

```
homepot-client/
├── backend/
│   ├── .env                      # Database connection string
│   ├── .env.example              # Example configuration
│   └── src/homepot/
│       ├── database.py           # Async database connection
│       ├── models.py             # SQLAlchemy models
│       ├── config.py             # Configuration management
│       └── app/db/database.py    # Sync database for API v1
└── scripts/
    └── init-postgresql.sh        # Database initialization
```

### Configuration

Database connections are configured in `backend/.env`:

```env
# PostgreSQL (Production & Development)
DATABASE__URL=postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db

# For testing, tests use in-memory SQLite databases automatically
# No TEST_DATABASE_URL configuration needed
```

## Database Management

### Common Operations

#### View Database Contents

```bash
# Using psql command line
export PGPASSWORD='homepot_dev_password'
psql -h localhost -U homepot_user -d homepot_db

# List all tables
\dt

# Show table structure
\d sites

# Run queries
SELECT * FROM sites;

# Exit
\q
```

#### Backup Database

```bash
# Create SQL dump
export PGPASSWORD='homepot_dev_password'
pg_dump -h localhost -U homepot_user homepot_db > backup_$(date +%Y%m%d).sql

# Restore from backup
psql -h localhost -U homepot_user -d homepot_db < backup.sql
```

#### Reset to Demo Data

```bash
# Drop and recreate database with demo data
./scripts/init-postgresql.sh
```

### Environment-Specific Databases

#### Development
- **Type**: PostgreSQL
- **Database**: `homepot_db`
- **Location**: `/var/lib/postgresql/16/main/`
- **Purpose**: Demo data and development testing
- **Contains**: 3 sites, 12 devices, 1 test user

#### Testing
- **Type**: SQLite (in-memory, temporary)
- **Purpose**: Automated test isolation
- **Contains**: Clean test data, created and destroyed per test run

#### Production
- **Type**: PostgreSQL
- **Purpose**: Live deployment
- **Configuration**: Via `DATABASE__URL` environment variable

## Testing

### Database Testing Strategy

```python
# Test database isolation
import pytest
from src.homepot.database import get_test_db

@pytest.fixture
def db_session():
    """Provide clean database session for each test."""
    db = get_test_db()
    yield db
    db.rollback()  # Clean up after test

def test_site_creation(db_session):
    """Test creating a new site."""
    site = Site(name="test-site", location="Test City")
    db_session.add(site)
    db_session.commit()
    
    assert site.id is not None
    assert site.name == "test-site"
```

### Running Database Tests

```bash
# Run all database tests
pytest backend/tests/test_database.py -v

# Run with database reset
pytest backend/tests/ --reset-db

# Test specific functionality
pytest backend/tests/test_models.py::test_site_device_relationship
```

## Demo Data Overview

The included demo database provides realistic test data:

### Sites (14 locations)
- Restaurant chain locations: `site-123`, `site-456`, etc.
- Distributed across different regions
- Each site configured with multiple POS terminals

### Devices (30 POS terminals)
- 5 terminals per site on average
- Named pattern: `pos-terminal-1` through `pos-terminal-5`
- Various status states for testing

### Jobs (13 recent jobs)
- Payment configuration updates
- Software deployment tasks
- Job status progression: `queued` → `sent` → `acknowledged` → `completed`

### Health Checks (68 records)
- Regular device monitoring data
- Performance metrics and status
- Demonstrates monitoring capabilities

## Advanced Usage

### Adding More Sites and Devices

As you test the platform, you may want to add more sites and devices beyond the initial demo data (2 sites, 8 devices). There are several ways to do this:

#### Method 1: Using the REST API (Recommended)

The easiest way to add data is through the REST API when the server is running.

**Start the server:**
```bash
cd backend
python -m uvicorn homepot.main:app --reload --host 0.0.0.0 --port 8000
```

**Add a new site:**
```bash
curl -X POST "http://localhost:8000/sites" \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "site-003",
    "name": "North Branch",
    "description": "Northern retail location with 4 POS terminals",
    "location": "789 North Ave, North Side"
  }'
```

**Add devices to the site:**
```bash
# First, get the site's internal ID from the response above or query sites
curl http://localhost:8000/sites

# Then add devices (replace {site_internal_id} with actual ID, e.g., 3)
curl -X POST "http://localhost:8000/devices" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pos-terminal-009",
    "name": "POS Terminal 9",
    "device_type": "pos_terminal",
    "site_id": 3,
    "ip_address": "192.168.3.9",
    "mac_address": "00:1B:44:11:3A:B9",
    "config": {
      "gateway_url": "https://payments.example.com"
    }
  }'
```

**Verify:**
```bash
curl http://localhost:8000/sites | python3 -m json.tool
curl http://localhost:8000/devices | python3 -m json.tool
```

#### Method 2: Using Python Script

Create a script to bulk-add data:

```python
# scripts/add_bulk_data.py
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from homepot.database import DatabaseService
from homepot.models import DeviceType

async def add_bulk_data():
    """Add multiple sites and devices."""
    db_service = DatabaseService()
    
    # Add 3 new sites
    sites_data = [
        {
            "site_id": "site-003",
            "name": "North Branch",
            "description": "Northern retail location",
            "location": "789 North Ave"
        },
        {
            "site_id": "site-004",
            "name": "South Branch",
            "description": "Southern retail location",
            "location": "321 South St"
        },
        {
            "site_id": "site-005",
            "name": "East Branch",
            "description": "Eastern retail location",
            "location": "555 East Blvd"
        }
    ]
    
    created_sites = []
    for site_data in sites_data:
        site = await db_service.create_site(**site_data)
        created_sites.append(site)
        print(f"Created site: {site.name} (ID: {site.id})")
    
    # Add devices to each new site
    device_counter = 9  # Start after existing 8 devices
    for site in created_sites:
        for i in range(1, 5):  # 4 devices per site
            device = await db_service.create_device(
                device_id=f"pos-terminal-{device_counter:03d}",
                name=f"POS Terminal {device_counter}",
                device_type=DeviceType.POS_TERMINAL,
                site_id=site.id,
                ip_address=f"192.168.{site.id}.{10+i}",
                config={"gateway_url": "https://payments.example.com"}
            )
            print(f"  Created device: {device.name}")
            device_counter += 1
    
    print(f"\nSuccessfully added {len(created_sites)} sites and {(device_counter-9)} devices!")

if __name__ == "__main__":
    asyncio.run(add_bulk_data())
```

**Run the script:**
```bash
# From project root
python scripts/add_bulk_data.py
```

#### Method 3: Modify init-postgresql.sh

For permanent demo data changes, edit the initialization script:

```bash
# Edit scripts/init-postgresql.sh
nano scripts/init-postgresql.sh

# Find the section that creates demo sites and devices
# Add your custom sites/devices there

# Then recreate the database
./scripts/init-postgresql.sh
```

#### Method 4: Direct SQL (Advanced)

For quick testing, you can insert data directly:

```bash
export PGPASSWORD='homepot_dev_password'
psql -h localhost -U homepot_user -d homepot_db
```

```sql
-- Add a new site
INSERT INTO sites (site_id, name, description, location, created_at, updated_at)
VALUES ('site-006', 'Quick Test Site', 'Test location', '123 Test St', 
        datetime('now'), datetime('now'));

-- Get the site's internal ID
SELECT id FROM sites WHERE site_id = 'site-006';

-- Add a device (replace {site_internal_id} with actual ID)
INSERT INTO devices (device_id, name, device_type, site_id, ip_address, 
                     status, created_at, updated_at)
VALUES ('pos-terminal-020', 'Test Terminal', 'pos_terminal', 
        6, '192.168.6.10', 'online', datetime('now'), datetime('now'));

-- Verify
SELECT s.name, COUNT(d.id) as device_count 
FROM sites s 
LEFT JOIN devices d ON s.id = d.site_id 
GROUP BY s.id;

.quit
```

#### Example: Create 10 Sites with 50 Devices

```python
# scripts/create_large_dataset.py
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from homepot.database import DatabaseService
from homepot.models import DeviceType

async def create_large_dataset():
    """Create 10 sites with 5 devices each (50 devices total)."""
    db_service = DatabaseService()
    
    device_counter = 1
    
    for site_num in range(1, 11):  # 10 sites
        # Create site
        site = await db_service.create_site(
            site_id=f"site-{site_num:03d}",
            name=f"Store Location {site_num}",
            description=f"Retail store #{site_num} with 5 POS terminals",
            location=f"{site_num * 100} Main Street, City {site_num}"
        )
        print(f"Created site: {site.name}")
        
        # Create 5 devices per site
        for device_num in range(1, 6):
            device = await db_service.create_device(
                device_id=f"pos-terminal-{device_counter:03d}",
                name=f"POS Terminal {device_counter}",
                device_type=DeviceType.POS_TERMINAL,
                site_id=site.id,
                ip_address=f"192.168.{site_num}.{10+device_num}",
                mac_address=f"00:1B:44:11:{site_num:02X}:{device_num:02X}",
                config={
                    "gateway_url": "https://payments.example.com",
                    "store_id": f"store-{site_num:03d}",
                    "terminal_id": f"term-{device_counter:03d}"
                }
            )
            print(f"  Created device: {device.name}")
            device_counter += 1
    
    print(f"\nSuccessfully created 10 sites and 50 devices!")
    print(f"Total in database: {site_num} sites, {device_counter-1} devices")

if __name__ == "__main__":
    asyncio.run(create_large_dataset())
```

**Run it:**
```bash
python scripts/create_large_dataset.py
```

#### Interactive API Documentation

Use the built-in Swagger UI for interactive data creation:

1. **Start the server:**
   ```bash
   cd backend
   python -m uvicorn homepot.main:app --reload
   ```

2. **Open browser:** [http://localhost:8000/docs](http://localhost:8000/docs)

3. **Create sites and devices interactively:**
   - Click on `POST /sites` endpoint
   - Click "Try it out"
   - Enter site data in JSON format
   - Click "Execute"
   - Copy the returned site `id` for device creation
   - Repeat for `POST /devices`

#### Verify Your Data

After adding data, verify the counts:

```bash
# Quick check via API
curl http://localhost:8000/sites | python3 -m json.tool | grep -c "site_id"
curl http://localhost:8000/devices | python3 -m json.tool | grep -c "device_id"

# Detailed check with psql
export PGPASSWORD='homepot_dev_password'
psql -h localhost -U homepot_user -d homepot_db << 'EOF'
SELECT 
  COUNT(DISTINCT s.id) as total_sites,
  COUNT(d.id) as total_devices,
  ROUND(AVG(device_count)::numeric, 2) as avg_devices_per_site
FROM sites s
LEFT JOIN devices d ON s.id = d.site_id
LEFT JOIN (
  SELECT site_id, COUNT(*) as device_count 
  FROM devices 
  GROUP BY site_id
) dc ON s.id = dc.site_id;
EOF
```

## User Management

### Creating Test Users

Users can be created through the API or directly in the database. For testing, you can create users with Python:

#### Method 1: Using Python Script

Create a file `create_user.py`:

```python
import asyncio
import sys
from pathlib import Path
import bcrypt

# Setup path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir / "src"))

from homepot.database import DatabaseService
from homepot.models import User

async def create_user(username, email, password, is_admin=False):
    """Create a user with hashed password."""
    # Hash password with bcrypt
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    
    # Create user in database
    db = DatabaseService()
    try:
        async with db.get_session() as session:
            from sqlalchemy import select
            
            # Check if user exists
            result = await session.execute(
                select(User).where(User.email == email)
            )
            if result.scalar_one_or_none():
                print(f"User {email} already exists!")
                return
            
            # Create new user
            new_user = User(
                username=username,
                email=email,
                hashed_password=hashed_password,
                is_admin=is_admin,
                is_active=True
            )
            session.add(new_user)
            await session.commit()
            print(f"Created user: {username} ({email})")
    finally:
        await db.close()

# Run from project root
asyncio.run(create_user("testuser", "test@homepot.com", "Test123!", is_admin=True))
```

Run it:
```bash
cd backend  # Important: run from backend directory for .env loading
python ../create_user.py
```

#### Method 2: Using API Signup Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@homepot.com",
    "password": "Test123!",
    "is_admin": true
  }'
```

#### Method 3: Direct SQL (Not Recommended)

**Warning:** Direct SQL bypasses password hashing. Only use for understanding schema.

```sql
-- View users
SELECT id, username, email, is_admin, is_active, created_at 
FROM users;

-- Check password hash format
SELECT id, username, LEFT(hashed_password, 30) as hash_sample
FROM users;
```

### Viewing Users

```bash
# Using psql
export PGPASSWORD='homepot_dev_password'
psql -h localhost -U homepot_user -d homepot_db -c "
  SELECT id, username, email, is_admin, is_active, created_at 
  FROM users 
  ORDER BY created_at DESC;
"

# Using query helper script
./scripts/query-db.sh users
```

### Password Security

HOMEPOT uses **bcrypt** for password hashing:

- **Hashed passwords** are stored (e.g., `$2b$12$gC6leMKvDICuZ...`)
- **Never** stored in plain text
- **Cannot be reversed** to see original password
- **Secure** even if database is compromised

Example hashed password structure:
```
$2b$12$gC6leMKvDICuZ6IsAxypFuelJgy8B85ropxHhOFpsJR...
│   │  │
│   │  └─ Salt (22 chars)
│   └──── Cost factor (2^12 iterations)
└──────── Algorithm (bcrypt)
```

### Custom Queries

```python
from src.homepot.database import get_db
from src.homepot.models import Site, Device

# Get all sites with device counts
db = get_db()
sites_with_devices = (
    db.query(Site)
    .join(Device)
    .group_by(Site.id)
    .all()
)

# Find inactive devices
inactive_devices = (
    db.query(Device)
    .filter(Device.status == 'offline')
    .all()
)
```

### Database Migrations (Future)

When schema changes are needed:

```bash
# Create migration
alembic revision --autogenerate -m "Add new table"

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

## Docker Usage

### Database Persistence

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:16
    environment:
      - POSTGRES_DB=homepot
      - POSTGRES_USER=homepot_user
      - POSTGRES_PASSWORD=homepot_dev_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  homepot-api:
    depends_on:
      - db
    environment:
      - DATABASE__URL=postgresql://homepot_user:homepot_dev_password@db:5432/homepot

volumes:
  postgres_data:
```

### Using PostgreSQL in Docker

```bash
# Start PostgreSQL container
docker-compose up -d db

# Access database
docker-compose exec db psql -U homepot_user -d homepot

# View logs
docker-compose logs db
```

## Security Considerations

### Development
- Use local PostgreSQL with development credentials
- Development database accessible only on localhost
- Demo data is non-sensitive

### Production
- Use strong passwords for PostgreSQL
- Enable SSL/TLS for database connections
- Regular backups and monitoring
- Network-level access controls
- Environment-based configuration

### Best Practices

```python
# Always use environment variables for sensitive data
DATABASE__URL = os.getenv("DATABASE__URL")  # From .env file
```
```
```

### Production PostgreSQL

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: homepot
      POSTGRES_USER: homepot_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  homepot-client:
    environment:
      - DATABASE_URL=postgresql://homepot_user:${POSTGRES_PASSWORD}@postgres:5432/homepot
```

## Security Considerations

### Development
- Use local PostgreSQL with development credentials
- Development database accessible only on localhost
- Demo data is non-sensitive

### Production
- Use PostgreSQL with proper authentication
- Enable SSL/TLS for database connections
- Regular backups and monitoring
- Environment-based configuration

### Best Practices

```python
# Always use environment variables for sensitive data
from homepot.config import get_settings

settings = get_settings()
db_url = settings.database.url  # From DATABASE__URL

# Use connection pooling for production
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
```

## Related Documentation

- **[Getting Started](getting-started.md)** - Initial setup and configuration
- **[Development Guide](development-guide.md)** - Development workflow
- **[Deployment Guide](deployment-guide.md)** - Production deployment
- **[POS Management](pos-management.md)** - Device and site management

## Troubleshooting

### Common Issues

**Cannot connect to database:**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Restart PostgreSQL if needed
sudo systemctl restart postgresql

# Verify connection settings
psql -h localhost -U homepot_user -d homepot_db
```

**Database doesn't exist:**
```bash
# Solution: Initialize the database
./scripts/init-postgresql.sh
```

**Permission errors:**
```bash
# Solution: Verify PostgreSQL user permissions
sudo -u postgres psql -c "\du homepot_user"

# Re-grant permissions if needed
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE homepot_db TO homepot_user;"
```

### Performance Tips

- Use indexes for frequently queried fields
- Monitor query performance with `EXPLAIN ANALYZE`
- Consider connection pooling for high-load scenarios (already configured in SQLAlchemy)
- Regular database maintenance: `VACUUM ANALYZE`
- Monitor PostgreSQL logs: `/var/log/postgresql/`

### Scalability Patterns

To handle large datasets efficiently, the system implements the following patterns:

#### Pagination for Large Result Sets
When retrieving large numbers of records (e.g., devices for a site), use pagination to avoid memory issues. The `DatabaseService` provides methods like `get_devices_by_site_and_segment_paginated` which utilize `LIMIT` and `OFFSET` at the database level.

```python
# Example of paginated retrieval
batch_size = 50
offset = 0
while True:
    devices = await db_service.get_devices_by_site_and_segment_paginated(
        site_id="site-123",
        limit=batch_size,
        offset=offset
    )
    if not devices:
        break
    
    # Process batch...
    offset += batch_size
```

#### Batch Processing
Operations that affect many rows should be batched to manage transaction size and lock duration. The job orchestrator uses this pattern for sending push notifications to large device segments.

### Support

For database-related issues:
1. Check PostgreSQL logs: `/var/log/postgresql/postgresql-16-main.log`
2. Verify database configuration in `backend/.env`
3. Test with a fresh database: `./scripts/init-postgresql.sh`
4. Review configuration settings
5. Check environment variables

---

*This guide covers the essential database operations for HOMEPOT. For advanced topics or specific issues, refer to the individual component documentation or create an issue in the project repository.*
