#!/bin/bash

################################################################################
# HOMEPOT User App Startup Script
#
# This script starts the HOMEPOT User App (Agent) locally.
#
# Usage: ./scripts/start-userapp.sh
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Get script directory and repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                                ║${NC}"
echo -e "${CYAN}║                  HOMEPOT USER APP SETUP                        ║${NC}"
echo -e "${CYAN}║                                                                ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

################################################################################
# Helper Functions
################################################################################

print_step() {
    echo -e "\n${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${CYAN}ℹ${NC} $1"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

port_in_use() {
    lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1
}

################################################################################
# Prerequisites Check
################################################################################

print_step "Checking prerequisites..."

# Check Node.js
if ! command_exists node; then
    print_error "Node.js is not installed"
    exit 1
fi
print_success "Node.js found: $(node --version)"

# Check npm
if ! command_exists npm; then
    print_error "npm is not installed"
    exit 1
fi
print_success "npm found: $(npm --version)"

################################################################################
# Port Availability Check
################################################################################

print_step "Checking port availability..."

if port_in_use 5174; then
    print_warning "Port 5174 is already in use"
    read -p "Kill existing process and continue? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        lsof -ti:5174 | xargs kill -9 2>/dev/null || true
        sleep 1
        print_success "Killed existing process on port 5174"
    else
        print_error "Cannot start User App - port 5174 is in use"
        exit 1
    fi
else
    print_success "Port 5174 is available"
fi

################################################################################
# User App Setup
################################################################################

print_step "Setting up User App..."

cd "$REPO_ROOT/user_app"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    print_info "Installing dependencies..."
    npm install
    print_success "Dependencies installed"
fi

################################################################################
# Start Services
################################################################################

print_step "Starting User App..."

# Create log directory if it does not exist
mkdir -p "$REPO_ROOT/logs"

# Ensure we're using Node 22 if nvm is available
if command_exists nvm; then
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm use 22 2>/dev/null || true
fi

print_info "Starting User App server on http://localhost:5174..."
nohup npm run dev > "$REPO_ROOT/logs/userapp.log" 2>&1 &
USERAPP_PID=$!
echo $USERAPP_PID > "$REPO_ROOT/logs/userapp.pid"

# Wait for server to start
sleep 3

# Check if server started successfully
if ps -p $USERAPP_PID > /dev/null; then
    print_success "User App started successfully (PID: $USERAPP_PID)"
else
    print_error "User App failed to start"
    print_info "Check logs: $REPO_ROOT/logs/userapp.log"
    exit 1
fi

################################################################################
# Summary
################################################################################

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                                ║${NC}"
echo -e "${CYAN}║                        SETUP COMPLETE!                         ║${NC}"
echo -e "${CYAN}║                                                                ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Process ID:${NC}"
echo -e "  User App: $USERAPP_PID"
echo ""
echo -e "${GREEN}Log File:${NC}"
echo -e "  User App: $REPO_ROOT/logs/userapp.log"
echo ""
echo -e "${YELLOW}Quick Commands:${NC}"
echo -e "  ${CYAN}View logs:${NC}  tail -f $REPO_ROOT/logs/userapp.log"
echo -e "  ${CYAN}Stop app:${NC}   kill \$(cat $REPO_ROOT/logs/userapp.pid)"
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo -e "  1. User App is ready."
echo -e "  2. Please open ${BLUE}http://localhost:5174${NC} manually in your browser."
echo ""
exit 0