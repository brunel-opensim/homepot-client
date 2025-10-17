# Database File Management - Permanent Solution

## Problem Solved

**Before:** The `data/homepot.db` file was tracked in git, causing merge conflicts on every run because:
- SQLite database files are binary (cannot be meaningfully merged)
- Database changes with every test run or development activity
- Different developers have different local data needs

**After:** Database files are now excluded from git. Each developer maintains their own local database.

## Implementation

### What Changed

1. **Updated `.gitignore`**
   - Now excludes `data/*.db` files
   - Excludes all SQLite temporary files (`.db-wal`, `.db-shm`)
   - Keeps backup directory structure but not backup files

2. **Created `scripts/init-database.sh`**
   - Initializes fresh database with schema
   - Creates demo sites and devices for testing
   - Automatically backs up existing database before recreating
   - Safe to run multiple times

3. **Created `data/README.md`**
   - Documents the database lifecycle
   - Explains why this approach is better
   - Provides troubleshooting guide

4. **Created `data/backups/` directory**
   - Stores database backups with timestamps
   - Backups are NOT tracked in git (local only)

### What's Tracked in Git

**Schema and code** (versioned):
- `src/homepot_client/models.py` - Database schema
- `src/homepot_client/database.py` - Database service
- `scripts/init-database.sh` - Initialization script
- `data/README.md` - Documentation
- `data/backups/.gitkeep` - Directory structure

**Runtime data** (not versioned):
- `data/homepot.db` - The actual database file
- `data/backups/*.db` - Backup files
- `data/*.db-wal` - SQLite write-ahead logs
- `data/*.db-shm` - SQLite shared memory

## Usage

### First Time Setup (After Clone)

```bash
# Initialize the database
./scripts/init-database.sh
```

This creates a fresh database with:
- All tables from schema
- 2 demo sites
- 8 demo POS devices

### Daily Development

```bash
# Work normally - database changes are local
pytest tests/
python -m homepot_client.main

# No database conflicts when pulling updates!
git pull origin main
```

### When Schema Changes

If someone updates the models (adds/removes tables/columns):

```bash
# Recreate your database with new schema
./scripts/init-database.sh

# Answer 'y' to backup and recreate
# Your old data is saved in data/backups/
```

### Manual Database Reset

```bash
# Option 1: Use the script (recommended)
./scripts/init-database.sh

# Option 2: Manual cleanup
rm data/homepot.db
./scripts/init-database.sh
```

## How This Solves Merge Conflicts

### Before (Tracking database.db):

```bash
git pull origin main
# Conflict in data/homepot.db
# CONFLICT (binary file merge conflict)
# Cannot merge binary files!
# Manual resolution required every time
```

### After (Not tracking database):

```bash
git pull origin main
# No conflicts - database is local only!
# Schema changes applied via init script
# Each developer has their own data
```

## Backup and Recovery

### Automatic Backups

Every time you run `./scripts/init-database.sh`, your existing database is automatically backed up:

```
data/backups/homepot_backup_20251017_143022.db
data/backups/homepot_backup_20251017_150145.db
```

### Restore from Backup

```bash
# List backups
ls -lh data/backups/

# Restore specific backup
cp data/backups/homepot_backup_TIMESTAMP.db data/homepot.db
```

## Future: Alembic Migrations

For production deployments, we can add **Alembic** for database migrations:

```bash
# Generate migration when models change
alembic revision --autogenerate -m "Add new column"

# Apply migration
alembic upgrade head
```

This allows:
- Versioned schema changes
- Data migration scripts
- Rollback capability
- Multiple environments (dev, staging, prod)

## Checklist for Team Members

When you first clone the repository:

- Run `./scripts/init-database.sh` to create your local database
- Verify `data/homepot.db` exists locally
- Confirm `data/homepot.db` is NOT in git status
- Read `data/README.md` for database documentation

When pulling updates:

- Check if `models.py` or `database.py` changed
- If schema changed, run `./scripts/init-database.sh` to update
- Your local data is preserved in backups/

When committing changes:

- Ensure `data/homepot.db` is NOT in `git status`
- Only commit schema changes (`models.py`, migrations)
- Update `init-database.sh` if seed data needs change
  