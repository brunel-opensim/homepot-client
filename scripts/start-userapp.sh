#!/bin/bash

################################################################################
# HOMEPOT User App Startup Script
#
# This script starts the HOMEPOT User App (Agent) locally.
#
# Usage: ./scripts/start-userapp.sh [--reset]
#
# Options:
#   -r, --reset   Clear stored device credentials and the emulator credential
#                 stash, then boot directly into the Setup wizard so a new
#                 device can be provisioned.
#   -h, --help    Show usage information.
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
PID_FILE="$REPO_ROOT/logs/userapp.pid"
LOG_FILE="$REPO_ROOT/logs/userapp.log"
ELECTRON_BIN="$REPO_ROOT/user_app/node_modules/electron/dist/electron"

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

userapp_ready() {
    local pid=$1
    ps -p "$pid" >/dev/null 2>&1 || return 1
    port_in_use 5174 || return 1
    if command_exists setsid; then
        # Linux: confirm the Electron child via process-group tracking.
        pgrep -g "$pid" -f "^$ELECTRON_BIN .* \\.$" >/dev/null 2>&1
    else
        # macOS has no setsid, so the Electron child shares the shell's
        # process group; a live npm wrapper + the Vite port is the readiness
        # signal here.
        return 0
    fi
}

################################################################################
# Command-line Arguments
################################################################################

RESET_MODE=false

show_help() {
    cat <<EOF
Usage: ./scripts/start-userapp.sh [--reset]

Starts the HOMEPOT User App (Agent) desktop application.

Options:
  -r, --reset   Clear stored device credentials and the emulator credential
                stash, then boot directly into the Setup wizard so a new
                device can be provisioned.
  -h, --help    Show this help message.
EOF
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        -r|--reset) RESET_MODE=true ;;
        -h|--help) show_help ;;
        *) print_error "Unknown argument: $arg"; show_help ;;
    esac
done

if [ "$RESET_MODE" = true ]; then
    print_step "Reset mode: clearing stored device credentials..."
    CREDENTIALS_FILE="$HOME/.homepot/credentials"
    if [ -f "$CREDENTIALS_FILE" ]; then
        rm -f "$CREDENTIALS_FILE"
        print_success "Removed $CREDENTIALS_FILE"
    else
        print_info "No stored credentials found at $CREDENTIALS_FILE"
    fi
    # The emulator engine persists its own credentials/config in
    # ~/.homepot/emulators/ (keyed by device name) and restores from them on
    # launch (_try_restore -> load_credentials). If a device was deleted on the
    # backend, leaving these behind makes a same-named emulator reuse a deleted
    # device_id and get 403s. Empty the stash so --reset yields a clean slate.
    EMULATOR_STASH="$HOME/.homepot/emulators"
    if [ -d "$EMULATOR_STASH" ]; then
        if rm -rf "$EMULATOR_STASH" 2>/dev/null; then
            print_success "Removed emulator credential stash $EMULATOR_STASH"
        else
            print_warning "Could not remove $EMULATOR_STASH"
        fi
    else
        print_info "No emulator credential stash found at $EMULATOR_STASH"
    fi
    "$SCRIPT_DIR/stop-userapp.sh" >/dev/null 2>&1 || true
fi

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

# setsid is Linux-only (util-linux); macOS falls back to nohup for process
# detachment, so it is not required.
for command in lsof pgrep; do
    if ! command_exists "$command"; then
        print_error "$command is required to manage the Electron User App lifecycle"
        exit 1
    fi
done

################################################################################
# Port Availability Check
################################################################################

print_step "Checking port availability..."

if [ -f "$PID_FILE" ]; then
    EXISTING_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ "$EXISTING_PID" =~ ^[0-9]+$ ]] && userapp_ready "$EXISTING_PID"; then
        print_success "Electron User App is already running (PID: $EXISTING_PID)"
        # The app holds a single-instance lock. Relaunching Electron briefly
        # triggers its 'second-instance' handler, which shows and focuses the
        # existing (possibly hidden, in-tray) window. Then it exits on its own.
        print_info "Reopening the User App window..."
        (
            cd "$REPO_ROOT/user_app"
            nohup "$ELECTRON_BIN" . --no-sandbox >/dev/null 2>&1 &
        )
        exit 0
    fi
    print_warning "Cleaning an incomplete or stale User App process"
    "$SCRIPT_DIR/stop-userapp.sh" >/dev/null 2>&1 || true
fi

# Clean Electron shells left by launchers from before process-group tracking.
LEGACY_ELECTRON_PIDS="$(pgrep -f "^$ELECTRON_BIN --no-sandbox \\.$" || true)"
if [ -n "$LEGACY_ELECTRON_PIDS" ]; then
    print_warning "Cleaning stale Electron process(es): $LEGACY_ELECTRON_PIDS"
    kill $LEGACY_ELECTRON_PIDS 2>/dev/null || true
fi

if port_in_use 5174; then
    print_warning "Port 5174 is already in use"
    read -p "Kill existing process and continue? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        lsof -ti:5174 | xargs kill 2>/dev/null || true
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

print_info "Starting Electron User App on http://localhost:5174..."
if command_exists setsid; then
    nohup setsid npm run electron:dev > "$LOG_FILE" 2>&1 &
else
    # macOS: no setsid, so detach with nohup only.
    nohup npm run electron:dev > "$LOG_FILE" 2>&1 &
fi
USERAPP_PID=$!
echo "$USERAPP_PID" > "$PID_FILE"

# Wait for Vite and the Electron main process, not only the npm wrapper.
for _ in {1..30}; do
    if userapp_ready "$USERAPP_PID"; then
        break
    fi
    if ! ps -p "$USERAPP_PID" >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

if userapp_ready "$USERAPP_PID"; then
    print_success "User App started successfully (PID: $USERAPP_PID)"
else
    print_error "User App failed to start"
    print_info "Check logs: $LOG_FILE"
    "$SCRIPT_DIR/stop-userapp.sh" >/dev/null 2>&1 || true
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
echo -e "  User App: $LOG_FILE"
echo ""
echo -e "${YELLOW}Quick Commands:${NC}"
echo -e "  ${CYAN}View logs:${NC}  tail -f $LOG_FILE"
echo -e "  ${CYAN}Stop app:${NC}   $SCRIPT_DIR/stop-userapp.sh"
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo -e "  1. The Electron User App is ready."
echo -e "  2. Complete setup in the ${BLUE}HOMEPOT Agent${NC} desktop window."
echo -e ""
echo -e "  ${YELLOW}Tip:${NC} To provision a new device later, stop the app and run"
echo -e "       ${CYAN}$SCRIPT_DIR/start-userapp.sh --reset${NC}"
echo ""
exit 0
