#!/bin/bash

################################################################################
# HOMEPOT Device Emulator Stop Script
#
# This script stops a background emulator started via start-emulator.sh.
#
# Usage: ./scripts/stop-emulator.sh
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

echo -e "${CYAN}Stopping HOMEPOT device emulator...${NC}\n"

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

# Stop emulator using PID file
kill_by_pidfile "$REPO_ROOT/logs/emulator.pid" "emulator"

# Fallback: kill any remaining emulator processes
pkill -f "emulators/linux_pos_emulator.py" 2>/dev/null \
    && echo -e "${GREEN}✓${NC} Killed remaining emulator processes"

echo ""
echo -e "${GREEN}HOMEPOT device emulator stopped.${NC}"
