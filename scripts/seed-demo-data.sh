#!/usr/bin/env bash
################################################################################
# HOMEPOT Demo Data Seeder
#
# Opt-in script that seeds the full demo dataset into an existing database:
# tenants, users, sites, simulated devices, and historical analytics data
# (metrics, alerts, jobs, audit, enrolment intents, operating schedules).
#
# A fresh database from ./scripts/init-postgresql.sh is intentionally CLEAN
# (schema + admin user only). Run this script only when you want the demo /
# simulated fleet. For real or emulated devices you do NOT need this.
#
# Usage: ./scripts/seed-demo-data.sh
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== HOMEPOT Demo Data Seeder ==="
echo ""

# Determine Python executable
PYTHON_CMD=""
if [ -f "$REPO_ROOT/.venv/bin/python3" ]; then
    PYTHON_CMD="$REPO_ROOT/.venv/bin/python3"
elif [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON_CMD="$REPO_ROOT/.venv/bin/python"
else
    PYTHON_CMD="python3"
fi

# Default database connection (matches init-postgresql.sh)
export DATABASE__URL="${DATABASE__URL:-postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db}"

echo ">> Running demo seed against $DATABASE__URL ..."
"$PYTHON_CMD" "$REPO_ROOT/backend/utils/seed_data.py"

echo ""
echo "=== Demo data seeding complete. ==="