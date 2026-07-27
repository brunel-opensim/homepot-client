#!/bin/bash
# Environment overrides for the HOMEPOT dev server.
# Source this file before starting services, or set EnvironmentFile= in systemd units.
#
# Usage:
#   source deploy/env-override.sh
#   systemctl start homepot-api

export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000,http://localhost:5173}"
export DATABASE__URL="${DATABASE__URL:-postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db}"
export SECRET_KEY="${SECRET_KEY:-homepot-dev-secret-change-in-production}"
export ENABLE_AGENT_SIMULATION="${ENABLE_AGENT_SIMULATION:-false}"
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
