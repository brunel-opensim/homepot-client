#!/bin/bash

################################################################################
# HOMEPOT Device Emulator Stop Script
#
# Stops emulator instances started via start-emulator.sh.
#
# Usage:
#   ./scripts/stop-emulator.sh              # stop ALL emulators
#   ./scripts/stop-emulator.sh <instance>   # stop one instance by name
#                                           #   (its --device-name, else type)
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

INSTANCE="${1:-}"

# Function to kill process by PID file
kill_by_pidfile() {
    local pidfile=$1
    local service=$2

    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if ps -p $pid > /dev/null 2>&1; then
            kill $pid 2>/dev/null
            sleep 1
            if ps -p $pid > /dev/null 2>&1; then
                kill -9 $pid 2>/dev/null
            fi
            echo -e "${GREEN}✓${NC} Stopped $service (PID: $pid)"
        else
            echo -e "${YELLOW}⚠${NC} $service was not running (stale PID file)"
        fi
        rm -f "$pidfile"
    else
        echo -e "${YELLOW}⚠${NC} No PID file found for $service"
    fi
}

if [ -n "$INSTANCE" ]; then
    # Stop a single instance by name (--device-name or emulator type)
    SLUG="$(printf '%s' "$INSTANCE" | tr ' /' '__')"
    echo -e "${CYAN}Stopping HOMEPOT device emulator '$INSTANCE'...${NC}\n"
    kill_by_pidfile "$REPO_ROOT/logs/emulator-${SLUG}.pid" "emulator ($INSTANCE)"
    echo ""
    echo -e "${GREEN}Emulator '$INSTANCE' stop requested.${NC}"
    exit 0
fi

# Stop ALL emulator instances
echo -e "${CYAN}Stopping HOMEPOT device emulators...${NC}\n"

for pidfile in "$REPO_ROOT"/logs/emulator-*.pid; do
    [ -e "$pidfile" ] || continue
    base=$(basename "$pidfile" .pid)
    kill_by_pidfile "$pidfile" "emulator ($base)"
done

# Back-compat: the pre-multi-instance single PID file
kill_by_pidfile "$REPO_ROOT/logs/emulator.pid" "emulator"

# Fallback: kill any remaining POS emulator processes (any OS wrapper or the engine)
if pkill -f "emulators/(linux|android|windows|macos|ios)_pos_emulator.py" 2>/dev/null \
    || pkill -f "emulators/pos_engine.py" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Killed remaining emulator processes"
fi

echo ""
echo -e "${GREEN}HOMEPOT device emulators stopped.${NC}"
