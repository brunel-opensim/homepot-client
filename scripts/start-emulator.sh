#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# start-emulator.sh — Launch a HOMEPOT device emulator in the background,
# logging to logs/emulator.log and recording its PID in logs/emulator.pid
# (mirrors start-userapp.sh).
#
# Usage:
#   ./scripts/start-emulator.sh                    # uses default (Linux) config
#   ./scripts/start-emulator.sh --emulator android # uses the Android emulator + config
#   ./scripts/start-emulator.sh --config emulators/my-device.json
#   ./scripts/start-emulator.sh --site-id site-it-demo1 --bootstrap-key <key> --device-name demo-pos-1
#
# Options:
#   --emulator linux|android|windows|macos|ios   Select the emulator script + default config
#                              (default: linux). Extend the map below for new OSes.
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

# --- Emulator & Config -------------------------------------------------------

# Map each OS emulator to its script stem + default config file. Optionally
# provide identity overrides that get passed to the emulator as flags, so a
# wrapper (e.g. the User App) or a plain launch always uses real OS identity.
declare -A EMULATORS=(
    [linux]="linux_pos:linux_pos_emulator.json"
    [android]="android_pos:android_pos_emulator.json"
    [windows]="windows_pos:windows_pos_emulator.json"
    [macos]="macos_pos:macos_pos_emulator.json"
    [ios]="ios_pos:ios_pos_emulator.json"
)

EMULATOR="linux"
FORWARD_ARGS=()
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --emulator)
            if [[ -z "${2:-}" ]] || [[ ! "${EMULATORS[$2]:-}" ]]; then
                echo "Error: unknown emulator '${2:-}'. Valid choices: ${!EMULATORS[*]}"
                exit 1
            fi
            EMULATOR="$2"
            shift 2
            ;;
        *)
            FORWARD_ARGS+=("$1")
            shift
            ;;
    esac
done
set -- "${FORWARD_ARGS[@]}"

EMULATOR_SCRIPT="emulators/${EMULATORS[$EMULATOR]%%:*}_emulator.py"
EMULATOR_CONFIG="emulators/${EMULATORS[$EMULATOR]#*:}"

CONFIG_ARGS=()
if [[ "$#" -eq 0 ]]; then
    CONFIG_ARGS=("--config" "$EMULATOR_CONFIG")

    # Fail fast when the default config still has placeholder values. Launching
    # with them makes provisioning fail on the backend (404 "Site not found")
    # after the process has already been backgrounded.
    if grep -q 'REPLACE_WITH_GENERATED_KEY' "$EMULATOR_CONFIG" \
        || grep -q '"site_id": "site-1"' "$EMULATOR_CONFIG"; then
        echo "Error: $EMULATOR_CONFIG still has placeholder values."
        echo "  The default site_id/key do not exist on the backend, so provisioning would fail."
        echo ""
        echo "  Either edit that file with a real site and bootstrap key, or launch with a key"
        echo "  generated for your site (POST /api/v1/sites/{site_id}/bootstrap-key):"
        echo ""
        echo "    ./scripts/start-emulator.sh --emulator $EMULATOR --site-id site-it-demo1 --bootstrap-key <key> --device-name demo-pos-1"
        echo ""
        echo "  Use a different --device-name per emulator to run several on one site."
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
echo "  Emulator: $EMULATOR_SCRIPT"
echo "  Python:   $PYTHON"
echo "  Config args: ${CONFIG_ARGS[*]:-} $*"
echo "  Log file: $LOG_FILE"
echo ""

nohup "$PYTHON" -u "$EMULATOR_SCRIPT" "${CONFIG_ARGS[@]}" "$@" \
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
