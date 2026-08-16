#!/bin/bash
# kpi-export.sh — run the versioned UK demonstrator KPI export from the repo
# root. Writes into kpi-evidence/ by default (gitignored, see
# kpi-evidence/README.md).
#
# Usage: ./scripts/kpi-export.sh --start <ISO> --end <ISO> [--out-dir DIR] [...]
set -euo pipefail

# Run from the repo root regardless of the caller's cwd.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Resolve the venv python (same pattern as init-postgresql.sh).
if [ -f ".venv/bin/python3" ]; then
    PYTHON=".venv/bin/python3"
elif [ -f "backend/.venv/bin/python3" ]; then
    PYTHON="backend/.venv/bin/python3"
else
    PYTHON="python3"
fi

# Load the database URL from backend/.env when the caller has not provided one
# (pydantic-settings only auto-loads ".env" from the current working directory).
if [ -z "${DATABASE__URL:-}" ] && [ -z "${DATABASE_URL:-}" ] && [ -f "backend/.env" ]; then
    DB_URL="$(grep -E '^DATABASE__URL=' backend/.env | head -1 | cut -d= -f2-)"
    if [ -n "$DB_URL" ]; then
        export DATABASE__URL="$DB_URL"
    fi
fi

PYTHONPATH=backend/src "$PYTHON" -m homepot.cli kpi-export "$@"
