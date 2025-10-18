# Database Guide

## Overview

The HOMEPOT system uses SQLite for development and testing, with PostgreSQL support for production deployments. This guide covers database setup, management, and usage patterns for the POS management system.

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

2. **Activate Environment**
   ```bash
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Database Ready!**
   The demo database (`data/homepot.db`) contains:
   - 14 restaurant sites
   - 30 POS terminals
   - Recent job history
   - Health monitoring data

4. **Test Connection**
   ```bash
   python -c "from src.homepot_client.database import get_db; print('Database connected!')"
   ```

## Database Organization

### File Structure

```
homepot-client/
├── data/                         # Database files
│   ├── homepot.db                # Main development database
│   ├── homepot_test.db           # Test database (auto-created)
│   └── migrations/               # Schema changes (future)
├── backend/homepot_client/
│   ├── database.py               # Database connection
│   ├── models.py                 # SQLAlchemy models
│   └── config.py                 # Database configuration
└── backend/tests/
    └── test_database.py          # Database tests
```

### Configuration

Database connections are configured in `backend/homepot_client/config.py`:

```python
# Development (default)
DATABASE_URL = "sqlite:///./data/homepot.db"

# Testing
TEST_DATABASE_URL = "sqlite:///./data/homepot_test.db"

# Production (environment variable)
PRODUCTION_DATABASE_URL = os.getenv("DATABASE_URL")
```

## Database Management

### Common Operations

#### View Database Contents

```bash
# Using SQLite command line
sqlite3 data/homepot.db
.tables                    # List all tables
.schema sites             # Show table structure
SELECT * FROM sites LIMIT 5;  # View sample data
.quit
```

#### Backup Database

```bash
# Create backup
cp data/homepot.db data/homepot_backup_$(date +%Y%m%d).db

# Or create SQL dump
sqlite3 data/homepot.db .dump > data/homepot_backup.sql
```

#### Reset to Demo Data

```bash
# Remove current database
rm data/homepot.db

# Restore from Git (if tracked)
git checkout data/homepot.db

# Or restore from backup
cp data/homepot_backup.db data/homepot.db
```

### Environment-Specific Databases

#### Development
- **File**: `data/homepot.db`
- **Purpose**: Demo data and development testing
- **Contains**: 14 sites, 30 devices, sample jobs

#### Testing
- **File**: `data/homepot_test.db`
- **Purpose**: Automated test isolation
- **Contains**: Clean test data, reset per test run

#### Production
- **Type**: PostgreSQL (recommended)
- **Purpose**: Live deployment
- **Configuration**: Via `DATABASE_URL` environment variable

## Testing

### Database Testing Strategy

```python
# Test database isolation
import pytest
from src.homepot_client.database import get_test_db

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
python -m uvicorn homepot_client.main:app --reload --host 0.0.0.0 --port 8000
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

from homepot_client.database import DatabaseService
from homepot_client.models import DeviceType

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
        print(f"✓ Created site: {site.name} (ID: {site.id})")
    
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
            print(f"  ✓ Created device: {device.name}")
            device_counter += 1
    
    print(f"\n✓ Successfully added {len(created_sites)} sites and {(device_counter-9)} devices!")

if __name__ == "__main__":
    asyncio.run(add_bulk_data())
```

**Run the script:**
```bash
# From project root
python scripts/add_bulk_data.py
```

#### Method 3: Modify init-database.sh

For permanent demo data changes, edit the initialization script:

```bash
# Edit scripts/init-database.sh
nano scripts/init-database.sh

# Find the section that creates demo sites and devices
# Add your custom sites/devices there

# Then recreate the database
./scripts/init-database.sh
```

#### Method 4: Direct SQL (Advanced)

For quick testing, you can insert data directly:

```bash
sqlite3 data/homepot.db
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

from homepot_client.database import DatabaseService
from homepot_client.models import DeviceType

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
        print(f"✓ Created site: {site.name}")
        
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
            print(f"  ✓ Created device: {device.name}")
            device_counter += 1
    
    print(f"\n✅ Successfully created 10 sites and 50 devices!")
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
   python -m uvicorn homepot_client.main:app --reload
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
# Quick check
curl http://localhost:8000/sites | python3 -m json.tool | grep -c "site_id"
curl http://localhost:8000/devices | python3 -m json.tool | grep -c "device_id"

# Detailed check with SQLite
sqlite3 data/homepot.db "
SELECT 
  COUNT(DISTINCT s.id) as total_sites,
  COUNT(d.id) as total_devices,
  ROUND(AVG(device_count), 2) as avg_devices_per_site
FROM sites s
LEFT JOIN devices d ON s.id = d.site_id
LEFT JOIN (
  SELECT site_id, COUNT(*) as device_count 
  FROM devices 
  GROUP BY site_id
) dc ON s.id = dc.site_id;
"
```

### Custom Queries

```python
from src.homepot_client.database import get_db
from src.homepot_client.models import Site, Device

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
  homepot-client:
    volumes:
      - ./data:/app/data        # Database persistence
    environment:
      - HOMEPOT_DATABASE_URL=sqlite:///app/data/homepot.db
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
- SQLite database is included in Git for demo purposes
- Contains only sample/demo data
- No sensitive information stored

### Production
- Use PostgreSQL with proper authentication
- Enable SSL/TLS for database connections
- Regular backups and monitoring
- Environment-based configuration

### Best Practices

```python
# Always use environment variables for sensitive data
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/homepot.db")

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

**Database locked error:**
```bash
# Solution: Close all connections and restart
pkill -f "homepot"
rm data/homepot.db-wal data/homepot.db-shm 2>/dev/null
```

**Missing database file:**
```bash
# Solution: Restore from Git or backup
git checkout data/homepot.db
# or
cp data/homepot_backup.db data/homepot.db
```

**Permission errors:**
```bash
# Solution: Fix file permissions
chmod 644 data/homepot.db
chmod 755 data/
```

### Performance Tips

- Use indexes for frequently queried fields
- Monitor query performance with `EXPLAIN QUERY PLAN`
- Consider connection pooling for high-load scenarios
- Regular database maintenance and analysis

### Support

For database-related issues:
1. Check the logs in `logs/` directory
2. Verify database file permissions
3. Test with a fresh database copy
4. Review configuration settings
5. Check environment variables

---

*This guide covers the essential database operations for HOMEPOT. For advanced topics or specific issues, refer to the individual component documentation or create an issue in the project repository.*
