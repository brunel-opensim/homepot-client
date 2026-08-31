#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Install the HOMEPOT Agent as a macOS launchd LaunchAgent.
#
# Usage:
#   ./scripts/install-agent-macos.sh              # install (current user)
#   ./scripts/install-agent-macos.sh --uninstall  # remove the service
#
# This script:
#   1. Installs the Python package (editable agent extra) if not present.
#   2. Creates /opt/homepot/{config,logs} (user-writable).
#   3. Installs the launchd plist into ~/Library/LaunchAgents.
#   4. Loads and starts the agent.
#
# The agent runs in the logged-in user's session so it can reach the local
# IPC server, AppleScript/volume controls, and user-scoped keychain.
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_NAME="com.homepot.agent.plist"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"
LABEL="com.homepot.agent"
HOMEPOT_DIR="/opt/homepot"

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
    info "Unloading $LABEL..."
    launchctl bootout "gui/$(id -u)" "$PLIST_DST" 2>/dev/null || \
        launchctl unload "$PLIST_DST" 2>/dev/null || true
    rm -f "$PLIST_DST"
    info "LaunchAgent removed."
    exit 0
fi

# ---- check prerequisites ---------------------------------------------------
if ! command -v launchctl &>/dev/null; then
    die "launchctl not found. This script only supports macOS."
fi
if [[ "$(uname -s)" != "Darwin" ]]; then
    die "This script only supports macOS (Darwin). See install-agent.sh for Linux."
fi

# ---- install Python package ------------------------------------------------
info "Installing homepot-agent Python package..."
cd "$REPO_ROOT/backend"
if [ -d ".venv" ]; then
    PIP=".venv/bin/pip"
    AGENT_BIN="$REPO_ROOT/backend/.venv/bin/homepot-agent"
else
    PIP="pip3"
    AGENT_BIN="$(command -v homepot-agent || echo /usr/local/bin/homepot-agent)"
fi

if ! command -v "${PIP}" >/dev/null 2>&1; then
    info "Installing editable agent extra into existing .venv"
    "$PIP" install -e ".[agent]"
fi

# ---- create data directories -----------------------------------------------
info "Creating $HOMEPOT_DIR/{config,logs}..."
sudo mkdir -p "$HOMEPOT_DIR/config" "$HOMEPOT_DIR/logs"
sudo chown -R "$(id -un):staff" "$HOMEPOT_DIR"
sudo chmod 0755 "$HOMEPOT_DIR"

# ---- ensure default agent config -------------------------------------------
DEFAULT_CONFIG="$HOMEPOT_DIR/config/agent-config.json"
if [ ! -f "$DEFAULT_CONFIG" ]; then
    info "Writing default agent config to $DEFAULT_CONFIG"
    cp "$REPO_ROOT/backend/src/homepot/agent/agent-config.json" "$DEFAULT_CONFIG"
    chmod 0600 "$DEFAULT_CONFIG"
fi

# ---- patch the plist to point at the real agent binary ---------------------
info "Installing LaunchAgent plist..."
mkdir -p "$HOME/Library/LaunchAgents"
sed "s|/usr/local/bin/homepot-agent|$AGENT_BIN|" "$PLIST_SRC" > "$PLIST_DST"

# ---- load and start --------------------------------------------------------
info "Loading $LABEL..."
launchctl bootout "gui/$(id -u)" "$PLIST_DST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"

echo ""
echo "HOMEPOT Agent installed successfully (macOS)."
echo "  LaunchAgent: $LABEL"
echo "  Plist:       $PLIST_DST"
echo "  Binary:      $AGENT_BIN"
echo "  Config:      $DEFAULT_CONFIG"
echo "  Logs:        $HOMEPOT_DIR/logs/"
echo ""
echo "Manage with:"
echo "  launchctl list | grep homepot"
echo "  launchctl kickstart gui/\$UID/$LABEL"
echo "  tail -f $HOMEPOT_DIR/logs/homepot-agent.stderr.log"
