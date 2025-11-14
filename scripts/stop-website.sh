#!/bin/bash

################################################################################
# HOMEPOT Website Stop Script
#
# This script stops both the backend and frontend servers.
#
# Usage: ./scripts/stop-website.sh
################################################################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory and repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${CYAN}Stopping HOMEPOT services...${NC}\n"

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

# Stop services using PID files
kill_by_pidfile "$REPO_ROOT/logs/backend.pid" "backend"
kill_by_pidfile "$REPO_ROOT/logs/frontend.pid" "frontend"

# Also kill by process name as backup
pkill -f "uvicorn homepot.app.main" 2>/dev/null && echo -e "${GREEN}✓${NC} Killed any remaining backend processes"
pkill -f "vite" 2>/dev/null && echo -e "${GREEN}✓${NC} Killed any remaining frontend processes"

echo ""
echo -e "${GREEN}All HOMEPOT services stopped.${NC}"
