# HOMEPOT Database Directory

This directory contains the SQLite database for HOMEPOT Client.

## 🚨 Important: Database Files Are NOT Tracked in Git

The database files (`*.db`) are **excluded from git** to prevent merge conflicts. Each developer/environment creates their own database.

## 🎯 Why This Approach?

**Problem:** Tracking database files in git causes:
- ❌ Merge conflicts on every run (binary files change)
- ❌ Large repository size (databases grow over time)  
- ❌ Cannot merge binary files meaningfully
- ❌ Different developers need different data

**Solution:** Track the **schema and initialization scripts**, not the database file itself.

## 📋 Quick Start

### First Time Setup

```bash
# Initialize a fresh database with schema and seed data
./scripts/init-database.sh
```

This will create:
- `homepot.db` - Main SQLite database
- All tables from the schema
- Demo sites and devices for testing

### Resetting Database

```bash
# Backup and recreate (script will prompt)
./scripts/init-database.sh

# Or manually:
rm data/homepot.db
./scripts/init-database.sh
```

## 📁 What's Tracked vs. Not Tracked

### ✅ Tracked in Git:
- Database initialization script (`scripts/init-database.sh`)
- Database models/schema (`src/homepot_client/models.py`)
- Database service layer (`src/homepot_client/database.py`)
- This README
- Backup directory structure (`backups/.gitkeep`)

### ❌ NOT Tracked in Git:
- `homepot.db` - Runtime database file
- `*.db-wal` - Write-Ahead Log files
- `*.db-shm` - Shared memory files
- `backups/*.db` - Database backups
- Any temporary database files

## 🔄 Database Lifecycle

### Development Workflow

1. **Clone repository** → No database exists
2. **Run init script** → `./scripts/init-database.sh`
3. **Work on code** → Database gets modified
4. **Commit changes** → Database NOT included (only code changes)
5. **Pull updates** → No database conflicts!
6. **Re-init if schema changes** → `./scripts/init-database.sh`

### When Schema Changes

If someone updates the database schema (adds tables, columns, etc.):

```bash
# You'll need to recreate your database
./scripts/init-database.sh
# Select 'y' to backup and recreate
```

Your old data will be backed up to `data/backups/`.

## 💾 Backups

Database backups are automatically created when re-initializing:

```bash
data/backups/
├── .gitkeep                          # Tracked (keeps directory)
├── homepot_backup_20251017_143022.db # NOT tracked
├── homepot_backup_20251017_150145.db # NOT tracked
└── ...
```

To restore from backup:
```bash
cp data/backups/homepot_backup_TIMESTAMP.db data/homepot.db
```

## 🏗️ Database Schema

The database schema is defined in `src/homepot_client/models.py`:

- **Sites** - Physical locations (stores, warehouses)
- **Devices** - POS terminals, IoT devices
- **Jobs** - Configuration update tasks
- **Users** - System users (if applicable)
- **AuditLog** - Audit trail for compliance
- **HealthCheck** - Device health monitoring

Schema is automatically created by the initialization script using SQLAlchemy's `create_all()`.

## 🛠️ Troubleshooting

### Database is locked
```bash
# Close all applications using the database
# Then try again
```

### Schema mismatch errors
```bash
# Your database schema is outdated
# Recreate the database
./scripts/init-database.sh
```

### Lost my data
```bash
# Check backups directory
ls -la data/backups/
# Restore from most recent backup
cp data/backups/homepot_backup_TIMESTAMP.db data/homepot.db
```

### Need to start fresh
```bash
# Remove database and backups
rm data/homepot.db
rm -rf data/backups/*.db
# Recreate
./scripts/init-database.sh
```

## 📚 Related Files

- `scripts/init-database.sh` - Database initialization script
- `src/homepot_client/models.py` - Database schema definitions
- `src/homepot_client/database.py` - Database service layer
- `.gitignore` - Excludes `*.db` files

## 🔍 Migration to Alembic (Future)

For production deployments, consider using **Alembic** for database migrations:

```bash
# Install Alembic (already in requirements.txt)
pip install alembic

# Initialize Alembic
alembic init alembic

# Generate migration from models
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

This allows versioned schema changes without losing data.
