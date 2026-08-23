#!/bin/bash

################################################################################
# HOMEPOT User App Stop Script
#
# This script stops the User App (Agent) server.
#
# Usage: ./scripts/stop-userapp.sh
################################################################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Get script directory and repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PID_FILE="$REPO_ROOT/logs/userapp.pid"
ELECTRON_BIN="$REPO_ROOT/user_app/node_modules/electron/dist/electron"

echo -e "${CYAN}Stopping HOMEPOT User App...${NC}\n"

if [ -f "$PID_FILE" ]; then
    USERAPP_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ "$USERAPP_PID" =~ ^[0-9]+$ ]] && ps -p "$USERAPP_PID" >/dev/null 2>&1; then
        USERAPP_PGID="$(ps -o pgid= -p "$USERAPP_PID" | tr -d ' ')"
        if [ "$USERAPP_PGID" = "$USERAPP_PID" ]; then
            kill -TERM -- "-$USERAPP_PGID" 2>/dev/null || true
            for _ in {1..20}; do
                ps -p "$USERAPP_PID" >/dev/null 2>&1 || break
                sleep 0.25
            done
            if ps -p "$USERAPP_PID" >/dev/null 2>&1; then
                kill -KILL -- "-$USERAPP_PGID" 2>/dev/null || true
            fi
            echo -e "${GREEN}✓${NC} Stopped User App process group (PID: $USERAPP_PID)"
        else
            kill "$USERAPP_PID" 2>/dev/null || true
            echo -e "${GREEN}✓${NC} Stopped legacy User App wrapper (PID: $USERAPP_PID)"
        fi
    else
        echo -e "${YELLOW}⚠${NC} User App was not running (stale PID file)"
    fi
    rm -f "$PID_FILE"
else
    echo -e "${YELLOW}⚠${NC} No PID file found for User App"
fi

# Compatibility cleanup for processes started before process-group tracking.
LEGACY_ELECTRON_PIDS="$(pgrep -f "^$ELECTRON_BIN --no-sandbox \\.$" || true)"
if [ -n "$LEGACY_ELECTRON_PIDS" ]; then
    kill $LEGACY_ELECTRON_PIDS 2>/dev/null || true
fi

LEGACY_EMULATOR_PIDS="$(pgrep -f "^$REPO_ROOT/.venv/bin/python3 $REPO_ROOT/emulators/(linux_pos|android_pos)_emulator.py --config $HOME/.homepot/emulators/.*-config.json$" || true)"
if [ -n "$LEGACY_EMULATOR_PIDS" ]; then
    kill $LEGACY_EMULATOR_PIDS 2>/dev/null || true
fi

# macOS: the Electron.app child is not in the tracked process group (no
# setsid) and its binary path differs from $ELECTRON_BIN, so it survives the
# wrapper kill above. Match the npm electron dist tree to fully quit it.
if [[ "$(uname)" == "Darwin" ]]; then
    pkill -f "$REPO_ROOT/user_app/node_modules/electron/dist" 2>/dev/null || true
fi

# Fallback: kill anything running on port 5174
if lsof -Pi :5174 -sTCP:LISTEN -t >/dev/null 2>&1; then
    lsof -ti:5174 | xargs kill 2>/dev/null
    echo -e "${GREEN}✓${NC} Killed remaining processes on port 5174"
fi

echo ""
echo -e "${GREEN}HOMEPOT User App stopped.${NC}"
