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
pytest tests/test_database.py -v

# Run with database reset
pytest tests/ --reset-db

# Test specific functionality
pytest tests/test_models.py::test_site_device_relationship
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
