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

echo -e "${CYAN}Stopping HOMEPOT User App...${NC}\n"

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

# Stop User App using PID file
kill_by_pidfile "$REPO_ROOT/logs/userapp.pid" "userapp"

# Fallback: kill anything running on port 5174
if lsof -Pi :5174 -sTCP:LISTEN -t >/dev/null 2>&1; then
    lsof -ti:5174 | xargs kill -9 2>/dev/null
    echo -e "${GREEN}✓${NC} Killed remaining processes on port 5174"
fi

echo ""
echo -e "${GREEN}HOMEPOT User App stopped.${NC}"
