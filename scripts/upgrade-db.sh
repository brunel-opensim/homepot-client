#!/bin/bash
# upgrade-db.sh — ensure the PostgreSQL database schema is at the latest
# alembic head, handling create_all-bootstrapped DBs and already-migrated DBs.
# The app bootstraps its base schema via SQLAlchemy `create_all()` at startup
# (database.py:190).  Migrations are additive on top of that base schema
# (CI check #249).  This script detects the current alembic state and applies
# any pending migrations, or records the state for a fresh create_all DB.
#
# Usage: bash scripts/upgrade-db.sh [--url DATABASE_URL]
set -euo pipefail

# ----- Resolve database URL -------------------------------------------------
URL=""
while (( "$#" )); do
  case "$1" in
    --url) URL="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# Precedence: CLI --url > DATABASE__URL env var > DATABASE_URL env var >
# config default (Postgres only, per repo migration).
if [ -n "$URL" ]; then
  export DATABASE__URL="$URL"
elif [ -n "${DATABASE__URL:-}" ]; then
  : # already set
elif [ -n "${DATABASE_URL:-}" ]; then
  export DATABASE__URL="$DATABASE_URL"
else
  # Config-driven Postgres default (DatabaseSettings defaults to Postgres).
  export DATABASE__URL="postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db"
fi

# The alembic CLI and psql need CWD = backend (script_location is relative
# to CWD, and .venv/bin/alembic is on PATH when running from the repo root).
cd backend

# ----- Detect alembic state -------------------------------------------------
# Each psql probe defaults to 0 on empty/failed output so the numeric
# comparisons below never see an empty string ("integer expression expected").
HAS_ALembIC_VERSION=$(psql "$DATABASE__URL" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='alembic_version'" 2>/dev/null | tr -d '[:space:]')
HAS_ALembIC_VERSION=${HAS_ALembIC_VERSION:-0}

HAS_TABLES=$(psql "$DATABASE__URL" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" 2>/dev/null | tr -d '[:space:]')
HAS_TABLES=${HAS_TABLES:-0}

# Check if the head-migration sentinel column exists:
# device_metrics.provenance is added by 20260815 and is present on any
# DB whose schema was bootstrapped by the current create_all models.
PROVENANCE_COL=$(psql "$DATABASE__URL" -tAc "SELECT count(*) FROM information_schema.columns WHERE table_name='device_metrics' AND column_name='provenance'" 2>/dev/null | tr -d '[:space:]')
PROVENANCE_COL=${PROVENANCE_COL:-0}

# ----- Apply the appropriate upgrade path ------------------------------------
if [ "$HAS_ALembIC_VERSION" -ge 1 ]; then
  # alembic_version exists → apply any pending additive migrations.
  # This covers the now-fixed live DB and any future DB that has had
  # alembic migrations applied.
  echo "=== upgrade-db: alembic_version present → running 'alembic upgrade head' ==="
  alembic -c alembic.ini upgrade head

elif [ "$HAS_TABLES" -eq 0 ]; then
  # No tables at all — a freshly-initialized DB (e.g. after
  # init-postgresql.sh before seed_data.py runs).  The app's
  # DatabaseService.initialize() will run create_all at startup,
  # so just stamp alembic head so the migration state is consistent.
  echo "=== upgrade-db: no tables → running 'alembic stamp head' ==="
  alembic -c alembic.ini stamp head
  echo "=== upgrade-db: fresh DB stamped; app create_all will bootstrap schema ==="

else
  # Legacy create_all DB: tables exist but no alembic_version.
  if [ "$PROVENANCE_COL" -ge 1 ]; then
    # Head-migration columns are already present → the create_all bootstrapped
    # from current models.  Just stamp head so alembic knows the state.
    echo "=== upgrade-db: head columns present → running 'alembic stamp head' ==="
    alembic -c alembic.ini stamp head
    echo "=== upgrade-db: schema state recorded; future migrations will be detected ==="
  else
    # Sentinels missing → DB was created with older models.  Stamp the base
    # revision (dna + heartbeat) then upgrade head to apply all additive
    # migrations from base to head.  This is the one-time remediation path
    # for stale DBs; after this run, alembic_version will be at head and
    # future schema PRs will only apply pending migrations.
    echo "=== upgrade-db: head columns missing → running 'alembic stamp 20260331_add_dna_heartbeat' then 'alembic upgrade head' ==="
    alembic -c alembic.ini stamp 20260331_add_dna_heartbeat
    alembic -c alembic.ini upgrade head
    echo "=== upgrade-db: baseline stamped and full upgrade complete ==="
  fi
fi

echo ""
echo "=== upgrade-db complete ==="
echo "DB URL: $DATABASE__URL"
echo "alembic_version: $(psql "$DATABASE__URL" -tAc 'SELECT version_num FROM alembic_version' 2>/dev/null | tr -d '[:space:]' || echo 'N/A')"
