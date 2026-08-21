#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# start-emulator.sh — Launch a HOMEPOT device emulator in the background.
#
# Each instance gets its own log/PID file, so several emulators can run at
# once (use a unique --device-name per instance).
#
# Usage:
#   ./scripts/start-emulator.sh                    # default (Linux) config
#   ./scripts/start-emulator.sh --emulator android # select emulator + config
#   ./scripts/start-emulator.sh --config emulators/my-device.json
#   ./scripts/start-emulator.sh --emulator macos \
#     --backend-url http://192.168.1.176:8000 \
#     --site-id SITE-7UAH-963T --bootstrap-key <key> --device-name demo-macos-1
#
# Options:
#   --emulator linux|android|windows|macos|ios   Select the emulator script + default config
#                              (default: linux). Extend the map below for new OSes.
#
#   All other arguments (--backend-url, --site-id, --bootstrap-key,
#   --device-name, --permission-consent-mode, ...) are forwarded to the
#   selected emulator. --device-name is also used to name the log/PID file.
#
# Log/PID files:
#   logs/emulator-<instance>.log   (instance = --device-name, else emulator type)
#   logs/emulator-<instance>.pid
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

# --- Instance slug ----------------------------------------------------------

# Derive a per-instance name from --device-name if provided, else the emulator
# type. This is used to give each running emulator its own log/PID file so
# several instances can run concurrently.
INSTANCE="$EMULATOR"
ARGS_COPY=("$@")
for ((i = 0; i < ${#ARGS_COPY[@]}; i++)); do
    if [[ "${ARGS_COPY[$i]}" == "--device-name" && -n "${ARGS_COPY[$((i + 1))]:-}" ]]; then
        INSTANCE="${ARGS_COPY[$((i + 1))]}"
        break
    fi
done
INSTANCE_SLUG="$(printf '%s' "$INSTANCE" | tr ' /' '__')"

# --- Logging ----------------------------------------------------------------

mkdir -p "$PROJECT_DIR/logs"
LOG_FILE="$PROJECT_DIR/logs/emulator-${INSTANCE_SLUG}.log"
PID_FILE="$PROJECT_DIR/logs/emulator-${INSTANCE_SLUG}.pid"

# --- Guard against duplicate instances ---------------------------------------

# Only guard this instance's own PID file, so different emulators can run
# simultaneously while a repeat launch of the same instance is refused.
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Error: emulator instance '$INSTANCE' is already running (PID $OLD_PID)"
        echo "  Stop it first: ./scripts/stop-emulator.sh $INSTANCE"
        exit 1
    fi
fi

# --- Run --------------------------------------------------------------------

echo "Starting HOMEPOT device emulator ..."
echo "  Emulator:  $EMULATOR_SCRIPT"
echo "  Instance:  $INSTANCE"
echo "  Python:    $PYTHON"
echo "  Config args: ${CONFIG_ARGS[*]:-} $*"
echo "  Log file:  $LOG_FILE"
echo "  PID file:  $PID_FILE"
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
echo "  Stop:       ./scripts/stop-emulator.sh $INSTANCE"
