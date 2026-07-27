#!/bin/bash
# HOMEPOT Dev Server — One-shot setup script.
#
# Prerequisites (installed by the OS package manager):
#   - Python 3.11+
#   - Node.js 22+
#   - PostgreSQL 16+
#
# Usage:
#   sudo ./scripts/setup-dev-server.sh
#
# This script is opinionated: it installs the project under /opt/homepot,
# creates a "homepot" system user, provisions the database, and enables
# systemd services.  Run it on a dedicated dev server or VM.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="${REPO_DIR}/deploy"
INSTALL_DIR="/opt/homepot"
VENV_DIR="${INSTALL_DIR}/.venv"
SERVICE_USER="homepot"

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[*]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[x]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------
log "Checking prerequisites..."

if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root (sudo)."
    exit 1
fi

for cmd in python3 node npm psql; do
    if ! command -v "$cmd" &>/dev/null; then
        err "'$cmd' not found.  Install it first:"
        err "  apt-get install python3 python3-venv nodejs postgresql"
        exit 1
    fi
done

PY_VER=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
if awk "BEGIN {exit !($PY_VER < 3.11)}"; then
    err "Python 3.11+ required (found $PY_VER)"
    exit 1
fi

echo "  python3 ... $(python3 --version)"
echo "  node   ... $(node --version)"
echo "  npm    ... $(npm --version)"
echo "  psql   ... $(psql --version 2>&1 | head -1)"

# ---------------------------------------------------------------------------
# Create homepot system user
# ---------------------------------------------------------------------------
log "Creating system user '${SERVICE_USER}'…"
if id "${SERVICE_USER}" &>/dev/null; then
    warn "User '${SERVICE_USER}' already exists — skipping."
else
    useradd --system --user-group --create-home --home-dir "${INSTALL_DIR}" "${SERVICE_USER}"
    log "User '${SERVICE_USER}' created with home '${INSTALL_DIR}'."
fi

# ---------------------------------------------------------------------------
# Copy project files
# ---------------------------------------------------------------------------
log "Copying project to ${INSTALL_DIR}…"
if [[ "${REPO_DIR}" != "${INSTALL_DIR}" ]]; then
    rsync -a --exclude='.venv' --exclude='node_modules' --exclude='__pycache__' \
        "${REPO_DIR}/" "${INSTALL_DIR}/"
    log "Project files copied."
else
    warn "Already running from ${INSTALL_DIR} — skipping copy."
fi

chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"

# ---------------------------------------------------------------------------
# Python virtual environment
# ---------------------------------------------------------------------------
log "Setting up Python virtual environment…"
if [[ -d "${VENV_DIR}" ]]; then
    warn "Virtual environment already exists — skipping."
else
    su -s /bin/bash "${SERVICE_USER}" -c "python3 -m venv '${VENV_DIR}'"
fi

log "Installing backend dependencies…"
su -s /bin/bash "${SERVICE_USER}" -c "'${VENV_DIR}/bin/pip' install --quiet -e '${INSTALL_DIR}/backend/'"

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
log "Installing frontend dependencies…"
su -s /bin/bash "${SERVICE_USER}" -c "cd '${INSTALL_DIR}/frontend' && npm install --quiet"

log "Building frontend…"
su -s /bin/bash "${SERVICE_USER}" -c "cd '${INSTALL_DIR}/frontend' && npm run build"

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
log "Configuring environment overrides…"
if [[ ! -f "${INSTALL_DIR}/deploy/env-override.sh" ]]; then
    cp "${DEPLOY_DIR}/env-override.sh" "${INSTALL_DIR}/deploy/env-override.sh"
fi

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
log "Initialising PostgreSQL database…"
if [[ -f "${INSTALL_DIR}/scripts/init-postgresql.sh" ]]; then
    su "${SERVICE_USER}" -c "'${INSTALL_DIR}/scripts/init-postgresql.sh'"
else
    warn "init-postgresql.sh not found — skipping database setup."
    warn "Run it later manually or create the database by hand."
fi

# ---------------------------------------------------------------------------
# Install systemd units
# ---------------------------------------------------------------------------
log "Installing systemd service units…"
for unit in homepot-api homepot-agent homepot-frontend; do
    cp "${DEPLOY_DIR}/${unit}.service" "/etc/systemd/system/${unit}.service"
    chmod 644 "/etc/systemd/system/${unit}.service"
done
systemctl daemon-reload

# ---------------------------------------------------------------------------
# Enable services
# ---------------------------------------------------------------------------
log "Enabling services…"
systemctl enable homepot-api
systemctl enable homepot-frontend
# Note: homepot-agent is NOT enabled by default — enable it only when a
# real device is attached to this dev server.

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  HOMEPOT dev server setup complete!${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Start services:"
echo "    sudo systemctl start homepot-api"
echo "    sudo systemctl start homepot-frontend"
echo ""
echo "  Check status:"
echo "    sudo systemctl status homepot-*"
echo ""
echo "  Follow logs:"
echo "    sudo journalctl -u homepot-api -f"
echo ""
echo "  API:      http://localhost:8000"
echo "  Dashboard: http://localhost:3000"
echo ""
echo "  Environment file: ${INSTALL_DIR}/deploy/env-override.sh"
echo "  Edit it to set your SECRET_KEY, DATABASE__URL, or CORS_ORIGINS."
echo ""
