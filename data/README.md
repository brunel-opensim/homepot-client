# HOMEPOT Database Directory

This directory is deprecated. HOMEPOT now uses PostgreSQL instead of SQLite.

## Migration Notice

**HOMEPOT has migrated from SQLite to PostgreSQL.** See [docs/postgresql-migration-complete.md](../docs/postgresql-migration-complete.md) for details.

## Database Setup

### PostgreSQL (Current)

```bash
# Initialize PostgreSQL database
./scripts/init-postgresql.sh
```

This creates:
- PostgreSQL database `homepot_db`
- User `homepot_user`
- All tables from schema
- 3 demo sites and 12 devices

### Connection

Database connection is configured in `backend/.env`:

```env
DATABASE__URL=postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db
```

## Database Management

### View Data

```bash
export PGPASSWORD='homepot_dev_password'
psql -h localhost -U homepot_user -d homepot_db
```

### Backup

```bash
export PGPASSWORD='homepot_dev_password'
pg_dump -h localhost -U homepot_user homepot_db > backup_$(date +%Y%m%d).sql
```

### Reset

```bash
./scripts/init-postgresql.sh
```

## Related Files

- `scripts/init-postgresql.sh` - PostgreSQL initialization
- `backend/src/homepot/models.py` - Database schema
- `backend/src/homepot/database.py` - Async database service
- `backend/.env` - Database configuration
