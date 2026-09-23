#!/bin/bash
# Environment overrides for the HOMEPOT dev server.
# Source this file before starting services, or set EnvironmentFile= in systemd units.
#
# Usage:
#   source deploy/env-override.sh
#   systemctl start homepot-api

export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000,http://localhost:5173}"
# ---------------------------------------------------------------------------
# REVERT WHEN PRODUCTION READY (trust -> password).
#
# Under HOMEPOT_DB_AUTH=trust the local trust in pg_hba.conf leaves the
# password out of the URL (there is no password).  This is the DEV phase.
# When the server team hardens auth (trust -> password / SCRAM) they will
# delete the trust branch below and restore the password-embedded default.
# See docs/server-deployment.md -> "PostgreSQL 16 Configuration" -> the
# "Revert trust" note that documents the one-line pg_hba.conf flip.
# ---------------------------------------------------------------------------
if [ "${HOMEPOT_DB_AUTH:-peer}" = "trust" ]; then
    export DATABASE__URL="${DATABASE__URL:-postgresql://homepot_user@localhost:5432/homepot_db}"
else
    export DATABASE__URL="${DATABASE__URL:-postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db}"
fi
export SECRET_KEY="${SECRET_KEY:-homepot-dev-secret-change-in-production}"
export ENABLE_AGENT_SIMULATION="${ENABLE_AGENT_SIMULATION:-false}"
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
