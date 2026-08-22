#!/usr/bin/env bash
################################################################################
# HOMEPOT Simulation Mode Switcher
#
# Seamlessly toggles the backend between the two data-source modes:
#
#   on  (simulation)  ENABLE_AGENT_SIMULATION=true  — the in-process agent
#                     simulator drives every active POS/IoT device (no emulator
#                     needed). Any running emulators are stopped first so they
#                     are not double-simulated.
#
#   off (emulation)   ENABLE_AGENT_SIMULATION=false — only real emulators /
#                     devices provide data. The backend no longer simulates.
#                     Start the emulator(s) yourself afterwards.
#
# Usage:
#   ./scripts/set-simulation-mode.sh on
#   ./scripts/set-simulation-mode.sh off
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$REPO_ROOT/.venv/bin/python"
ENV_FILE="$REPO_ROOT/backend/.env"
LOG_FILE="$REPO_ROOT/logs/backend.out"
PID_FILE="$REPO_ROOT/logs/backend.pid"

if [[ ! -f "$PYTHON" ]]; then
    echo "Error: Python virtual environment not found at .venv/"
    exit 1
fi

# --- Parse mode --------------------------------------------------------------

MODE="${1:-}"
case "$MODE" in
    on|true|1)  ENABLED="true";  MODE_LABEL="SIMULATION";;
    off|false|0) ENABLED="false"; MODE_LABEL="EMULATION";;
    *)
        echo "Usage: $0 on|off"
        echo "  on  = simulation mode (ENABLE_AGENT_SIMULATION=true)"
        echo "  off = emulation mode  (ENABLE_AGENT_SIMULATION=false)"
        exit 1
        ;;
esac

echo "=== Switching HOMEPOT backend to $MODE_LABEL mode ==="

# --- When going to simulation, stop any running emulators --------------------
# The simulator would otherwise also simulate the emulator's device (double
# data + provenance corruption).
if [[ "$ENABLED" == "true" ]] && [[ -x "$SCRIPT_DIR/stop-emulator.sh" ]]; then
    echo ">> Stopping any running emulators (simulator would double-simulate them)"
    "$SCRIPT_DIR/stop-emulator.sh" || true
fi

# --- Stop the backend --------------------------------------------------------
# Kill via PID file, the uvicorn reloader, and the multiprocessing worker
# (whose cmdline is 'spawn_main' and is missed by 'uvicorn' patterns).
kill_by_pidfile() {
    local pidfile=$1
    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(cat "$pidfile" 2>/dev/null || true)
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            sleep 1
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$pidfile"
    fi
}
kill_by_pidfile "$PID_FILE"
pkill -f "uvicorn homepot.app.main" 2>/dev/null || true
pkill -f "spawn_main" 2>/dev/null || true
sleep 2

echo ">> Updating $ENV_FILE -> ENABLE_AGENT_SIMULATION=$ENABLED"
if grep -q '^ENABLE_AGENT_SIMULATION=' "$ENV_FILE"; then
    sed -i.bak "s/^ENABLE_AGENT_SIMULATION=.*/ENABLE_AGENT_SIMULATION=$ENABLED/" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
else
    echo "ENABLE_AGENT_SIMULATION=$ENABLED" >> "$ENV_FILE"
fi

# --- Start the backend -------------------------------------------------------
echo ">> Starting backend ($MODE_LABEL mode)..."
mkdir -p "$REPO_ROOT/logs"
cd "$REPO_ROOT/backend"
setsid env ENABLE_AGENT_SIMULATION="$ENABLED" \
    "$PYTHON" -m uvicorn homepot.app.main:app \
    --host 0.0.0.0 --port 8000 \
    --reload --reload-dir src --reload-dir ../ai \
    --app-dir "$REPO_ROOT/backend/src" \
    > "$LOG_FILE" 2>&1 < /dev/null &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$PID_FILE"

echo ">> Waiting for the backend to come up..."
for _ in $(seq 1 30); do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health 2>/dev/null | grep -q "200"; then
        break
    fi
    sleep 1
done

if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health 2>/dev/null | grep -q "200"; then
    echo "=== Backend is up (PID $BACKEND_PID) in $MODE_LABEL mode ==="
    echo "  Log: tail -f $LOG_FILE"
else
    echo "Error: backend did not become healthy. Check logs: $LOG_FILE"
    exit 1
fi