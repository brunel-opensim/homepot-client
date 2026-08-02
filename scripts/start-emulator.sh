#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# start-emulator.sh — Launch a HOMEPOT device emulator in the background,
# logging to logs/emulator.log and recording its PID in logs/emulator.pid
# (mirrors start-userapp.sh).
#
# Usage:
#   ./scripts/start-emulator.sh                    # uses default config
#   ./scripts/start-emulator.sh --config emulators/my-device.json
#   ./scripts/start-emulator.sh --site-id site-it-demo1 --bootstrap-key <key>
#
# Prerequisites:
#   - Python virtual environment at .venv/ with httpx installed
#   - Backend running (start-dashboard.sh)
#   - A bootstrap key generated for the target site
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# --- Python & venv ----------------------------------------------------------

PYTHON=""
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -f ".venv/bin/python3" ]; then
    PYTHON=".venv/bin/python3"
else
    echo "Error: Python virtual environment not found at .venv/"
    echo "  Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e backend/."
    exit 1
fi

# --- Config -----------------------------------------------------------------

CONFIG_ARGS=()
if [[ "$#" -eq 0 ]]; then
    CONFIG_ARGS=("--config" "emulators/linux_pos_emulator.json")

    # Fail fast when the default config still has placeholder values. Launching
    # with them makes provisioning fail on the backend (404 "Site not found")
    # after the process has already been backgrounded.
    if grep -q 'REPLACE_WITH_GENERATED_KEY' emulators/linux_pos_emulator.json \
        || grep -q '"site_id": "site-1"' emulators/linux_pos_emulator.json; then
        echo "Error: emulators/linux_pos_emulator.json still has placeholder values."
        echo "  The default site_id/key do not exist on the backend, so provisioning would fail."
        echo ""
        echo "  Either edit that file with a real site and bootstrap key, or launch with a key"
        echo "  generated for your site (POST /api/v1/sites/{site_id}/bootstrap-key):"
        echo ""
        echo "    ./scripts/start-emulator.sh --site-id site-it-demo1 --bootstrap-key <key>"
        echo ""
        exit 1
    fi
fi

# --- Logging ----------------------------------------------------------------

mkdir -p "$PROJECT_DIR/logs"
LOG_FILE="$PROJECT_DIR/logs/emulator.log"
PID_FILE="$PROJECT_DIR/logs/emulator.pid"

# --- Guard against duplicate instances ---------------------------------------

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Error: an emulator is already running (PID $OLD_PID)"
        echo "  Stop it first: ./scripts/stop-emulator.sh"
        exit 1
    fi
fi

# --- Run --------------------------------------------------------------------

echo "Starting HOMEPOT device emulator ..."
echo "  Python: $PYTHON"
echo "  Config args: ${CONFIG_ARGS[*]:-} $*"
echo "  Log file: $LOG_FILE"
echo ""

nohup "$PYTHON" -u emulators/linux_pos_emulator.py "${CONFIG_ARGS[@]}" "$@" \
    > "$LOG_FILE" 2>&1 &
EMULATOR_PID=$!
echo "$EMULATOR_PID" > "$PID_FILE"

# Wait for provisioning / DNA registration (takes a few seconds)
sleep 4

if ! ps -p "$EMULATOR_PID" > /dev/null 2>&1; then
    echo "Error: emulator failed to start"
    echo "  Check logs: $LOG_FILE"
    exit 1
fi

echo "Emulator started (PID: $EMULATOR_PID)"
echo "  View logs:  tail -f $LOG_FILE"
echo "  Stop:       ./scripts/stop-emulator.sh"
