#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Install the HOMEPOT Agent as a systemd service on Linux.
#
# Usage:
#   sudo ./scripts/install-agent.sh              # install from repo checkout
#   sudo ./scripts/install-agent.sh --uninstall   # remove the service
#
# This script:
#   1. Installs the Python package into the system Python or a venv.
#   2. Creates the homepot system user.
#   3. Installs the systemd service unit.
#   4. Creates /var/lib/homepot for identity persistence.
#   5. Enables and starts the service.
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

INSTALL_PREFIX="${INSTALL_PREFIX:-/usr/local}"
SERVICE_NAME="homepot-agent"
SYSTEMD_DIR="/etc/systemd/system"
HOMEPOT_USER="homepot"
HOMEPOT_GROUP="homepot"
VAR_LIB="/var/lib/homepot"

# ---- helpers ---------------------------------------------------------------
die() { echo "[ERROR] $*" >&2; exit 1; }
info() { echo "[INFO] $*"; }

# ---- parse flags -----------------------------------------------------------
UNINSTALL=false
for arg in "$@"; do
    case "$arg" in
        --uninstall) UNINSTALL=true ;;
        --help) echo "Usage: $0 [--uninstall]" ; exit 0 ;;
    esac
done

# ---- uninstall -------------------------------------------------------------
if $UNINSTALL; then
    info "Stopping and disabling $SERVICE_NAME..."
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "$SYSTEMD_DIR/$SERVICE_NAME.service"
    systemctl daemon-reload
    info "Service removed."
    exit 0
fi

# ---- check prerequisites ---------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    die "This script must be run as root (sudo)."
fi

if ! command -v python3 &>/dev/null; then
    die "python3 is required but not found."
fi

if ! command -v systemctl &>/dev/null; then
    die "systemctl not found. This script only supports systemd-based systems."
fi

# ---- create system user ----------------------------------------------------
if ! id -u "$HOMEPOT_USER" &>/dev/null; then
    info "Creating system user '$HOMEPOT_USER'..."
    useradd --system --no-create-home --shell /usr/sbin/nologin "$HOMEPOT_USER"
fi

# ---- install Python package ------------------------------------------------
info "Installing homepot-agent Python package..."
cd "$REPO_ROOT/backend"

if [ -d ".venv" ]; then
    info "Using existing virtual environment at backend/.venv"
    PIP=".venv/bin/pip"
    PYTHON=".venv/bin/python"
else
    PIP="pip3"
    PYTHON="python3"
fi

$PIP install --upgrade pip
$PIP install -e ".[agent]"

# ---- create data directories -----------------------------------------------
info "Creating /var/lib/homepot..."
mkdir -p "$VAR_LIB"
chown "$HOMEPOT_USER:$HOMEPOT_GROUP" "$VAR_LIB"
chmod 0755 "$VAR_LIB"

# ---- install systemd unit --------------------------------------------------
info "Installing systemd service unit..."
cp "$SCRIPT_DIR/homepot-agent.service" "$SYSTEMD_DIR/$SERVICE_NAME.service"
chmod 0644 "$SYSTEMD_DIR/$SERVICE_NAME.service"

# Update the ExecStart to point to the installed agent binary
AGENT_BIN="$INSTALL_PREFIX/bin/homepot-agent"
sed -i "s|ExecStart=.*|ExecStart=$AGENT_BIN run|" "$SYSTEMD_DIR/$SERVICE_NAME.service"

systemctl daemon-reload

# ---- enable and start ------------------------------------------------------
info "Enabling and starting $SERVICE_NAME..."
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

info "Checking service status..."
systemctl status "$SERVICE_NAME" --no-pager || true

echo ""
echo "HOMEPOT Agent installed successfully."
echo "  Service:  $SERVICE_NAME"
echo "  Binary:   $AGENT_BIN"
echo "  Data:     $VAR_LIB"
echo ""
echo "Manage with:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
