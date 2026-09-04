#!/bin/bash

################################################################################
# HOMEPOT Complete Dashboard Startup Script
#
# This script starts both the backend and frontend servers for the complete
# HOMEPOT dashboard experience with full integration.
#
# Usage: ./scripts/start-dashboard.sh [simulation|emulation|real] [--backend-url URL]
#   simulation  Simulated devices via the in-process agent simulator (default)
#   emulation   Emulated devices via emulator processes started separately
#   real        Real devices — technician creates Sites/Bootstrap keys on
#               the Dashboard, then passes them to device owners who register
#               via the User App. No devices are added by default.
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory and repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                                ║${NC}"
echo -e "${CYAN}║                  HOMEPOT COMPLETE DASHBOARD SETUP              ║${NC}"
echo -e "${CYAN}║                                                                ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

################################################################################
# Mode selection
################################################################################
# The dashboard can run in three data-source modes:
#   simulation — the backend's in-process agent simulator drives the devices
#   emulation  — emulator processes (started separately) provide the data
#   real       — real device agents connect; no simulator, no default devices
#
# Emulation and real both require the simulator to be OFF; the difference is
# only what connects. The mode is persisted to backend/.env so the backend
# honours it regardless of how it is launched.
MODE="${1:-simulation}"
case "$MODE" in
    simulation)
        ENABLE_AGENT_SIMULATION="true"
        MODE_LABEL="SIMULATION"
        ;;
    emulation)
        ENABLE_AGENT_SIMULATION="false"
        MODE_LABEL="EMULATION"
        ;;
    real)
        ENABLE_AGENT_SIMULATION="false"
        MODE_LABEL="REAL"
        ;;
    *)
        echo "Usage: $0 [simulation|emulation|real] [--backend-url URL]"
        echo "  simulation  Simulated devices via the in-process agent simulator (default)"
        echo "  emulation   Emulated devices via emulator processes you start separately"
        echo "  real        Real devices — technician creates Sites/Bootstrap keys on"
        echo "              the Dashboard, then passes them to device owners via the User App"
        echo "  --backend-url URL  Base URL the backend advertises to devices (default: http://localhost:8000)"
        exit 1
        ;;
esac
echo -e "${CYAN}ℹ${NC} Mode: $MODE_LABEL (ENABLE_AGENT_SIMULATION=$ENABLE_AGENT_SIMULATION)"
echo ""

################################################################################
# Optional --backend-url (for real / emulation devices on the network)
################################################################################
BACKEND_URL="http://localhost:8000"
_ARGS=("$@")
for (( i=0; i<${#_ARGS[@]}; i++ )); do
    if [[ "${_ARGS[$i]}" == --backend-url=* ]]; then
        BACKEND_URL="${_ARGS[$i]#*=}"
    elif [[ "${_ARGS[$i]}" == "--backend-url" && $((i+1)) -lt ${#_ARGS[@]} ]]; then
        BACKEND_URL="${_ARGS[$((i+1))]}"
        (( i++ ))
    fi
done
echo -e "${CYAN}ℹ${NC} Backend URL for devices: $BACKEND_URL"
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

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if port is in use
port_in_use() {
    lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1
}

################################################################################
# Prerequisites Check
################################################################################

print_step "Checking prerequisites..."

# Check Python
if ! command_exists python3; then
    print_error "Python 3 is not installed"
    exit 1
fi
print_success "Python 3 found: $(python3 --version)"

# Check Node.js
if ! command_exists node; then
    print_error "Node.js is not installed"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 20 ]; then
    print_warning "Node.js version is $NODE_VERSION, but 22+ is recommended"
    if command_exists nvm; then
        print_info "Attempting to switch to Node.js 22 using nvm..."
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        nvm use 22 2>/dev/null || nvm install 22
    fi
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

if port_in_use 8000; then
    print_warning "Port 8000 is already in use (backend)"
    read -p "Kill existing process and continue? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        sleep 1
        print_success "Killed existing process on port 8000"
    else
        print_error "Cannot start backend - port 8000 is in use"
        echo -e "${YELLOW}Tip: Run ./scripts/stop-dashboard.sh to clean up old processes${NC}"
        exit 1
    fi
else
    print_success "Port 8000 is available (backend)"
fi

if port_in_use 5173; then
    print_warning "Port 5173 is in use (frontend will use next available port)"
fi

################################################################################
# Backend Setup
################################################################################

print_step "Setting up backend..."

# Activate virtual environment
if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
    print_info "Activating HOMEPOT virtual environment..."
    source "$REPO_ROOT/.venv/bin/activate"
    print_success "Virtual environment activated"
else
    print_error "Cannot find virtual environment at $REPO_ROOT/.venv"
    print_info "Please run ./scripts/install-backend.sh first"
    exit 1
fi

cd "$REPO_ROOT/backend"

# Check if uvicorn is installed
if ! python -c "import uvicorn" 2>/dev/null; then
    print_error "uvicorn is not installed in the virtual environment"
    print_info "Installing backend dependencies..."
    pip install -r requirements.txt
fi

################################################################################
# Frontend Setup
################################################################################

print_step "Setting up frontend..."

cd "$REPO_ROOT/frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    print_info "Installing frontend dependencies..."
    npm install
    print_success "Frontend dependencies installed"
fi

# Check .env.local exists
if [ ! -f ".env.local" ]; then
    print_warning ".env.local not found, creating from .env.example..."
    cp .env.example .env.local
    print_success "Created .env.local"
fi

################################################################################
# Start Services
################################################################################

print_step "Starting services..."

# Create log directory
mkdir -p "$REPO_ROOT/logs"

# Start backend in background
print_info "Starting backend server on http://localhost:8000..."
cd "$REPO_ROOT/backend"

# Persist the selected mode and backend URL to backend/.env so the
# backend honours them regardless of how it is launched afterwards.
ENV_FILE="$REPO_ROOT/backend/.env"
if [ -f "$ENV_FILE" ] && grep -q '^ENABLE_AGENT_SIMULATION=' "$ENV_FILE"; then
    sed -i.bak "s/^ENABLE_AGENT_SIMULATION=.*/ENABLE_AGENT_SIMULATION=$ENABLE_AGENT_SIMULATION/" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
else
    echo "ENABLE_AGENT_SIMULATION=$ENABLE_AGENT_SIMULATION" >> "$ENV_FILE"
fi
# Also persist the backend URL so devices know where to connect.
if [ -f "$ENV_FILE" ] && grep -q '^BACKEND_URL=' "$ENV_FILE"; then
    sed -i.bak "s/^BACKEND_URL=.*/BACKEND_URL=$BACKEND_URL/" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
else
    echo "BACKEND_URL=$BACKEND_URL" >> "$ENV_FILE"
fi

# Use bash -c to activate venv in the subshell
# Redirect stdout/stderr to backend.out (overwritten on start)
# The application handles backend.log with rotation
# --reload-dir watches the ai/ package (outside backend/) too, so edits to the
# AI gates/context code trigger an auto-restart alongside backend changes.
nohup bash -c "source $REPO_ROOT/.venv/bin/activate && ENABLE_AGENT_SIMULATION=$ENABLE_AGENT_SIMULATION HOMEPOT_BACKEND_URL=$BACKEND_URL python -m uvicorn homepot.app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir src --reload-dir ../ai" \
     > "$REPO_ROOT/logs/backend.out" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$REPO_ROOT/logs/backend.pid"

# Wait for backend to start (poll with retries)
print_step "Waiting for backend to initialize..."
BACKEND_READY=false
for i in $(seq 1 30); do
    sleep 2
    if ! ps -p $BACKEND_PID > /dev/null; then
        print_error "Backend process died during startup"
        print_info "Check startup logs: $REPO_ROOT/logs/backend.out"
        exit 1
    fi
    if curl -s http://localhost:8000/ > /dev/null 2>&1; then
        BACKEND_READY=true
        print_success "Backend started successfully (PID: $BACKEND_PID)"
        break
    fi
    if [ $((i % 5)) -eq 0 ]; then
        print_info "Still waiting for backend... ($((i * 2))s)"
    fi
done

if [ "$BACKEND_READY" != "true" ]; then
    print_error "Backend process is running but not responding"
    print_info "Check startup logs: $REPO_ROOT/logs/backend.out"
    print_info "Check app logs: $REPO_ROOT/logs/backend.log"
    exit 1
fi

# Start frontend in background
print_info "Starting frontend server on http://localhost:5173..."
cd "$REPO_ROOT/frontend"

# Ensure we're using Node 22 if nvm is available
if command_exists nvm; then
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm use 22 2>/dev/null || true
fi

nohup npm run dev > "$REPO_ROOT/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$REPO_ROOT/logs/frontend.pid"

# Wait for frontend to start
sleep 3

# Check if frontend started successfully
if ps -p $FRONTEND_PID > /dev/null; then
    print_success "Frontend started successfully (PID: $FRONTEND_PID)"
else
    print_error "Frontend failed to start"
    print_info "Check logs: $REPO_ROOT/logs/frontend.log"
    
    # Kill backend if frontend failed
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

################################################################################
# Verification
################################################################################

print_step "Verifying services..."

# Test backend
if curl -s http://localhost:8000/ | grep -q "Alive"; then
    print_success "Backend is responding"
else
    print_warning "Backend may not be fully ready yet"
fi

# Test frontend (just check if port is listening)
if port_in_use 5173 || port_in_use 5174; then
    print_success "Frontend is running"
else
    print_warning "Frontend port may not be ready yet"
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
echo -e "${GREEN}Services Started:${NC}"
echo -e "  ${BLUE}Backend:${NC}  http://localhost:8000"
echo -e "            API Docs: http://localhost:8000/docs"
echo -e "  ${BLUE}Frontend:${NC} http://localhost:5173"
echo ""
echo -e "${GREEN}Process IDs:${NC}"
echo -e "  Backend:  $BACKEND_PID"
echo -e "  Frontend: $FRONTEND_PID"
echo ""

echo -e "${GREEN}Mode:${NC} $MODE_LABEL"
case "$MODE" in
    simulation)
        echo -e "  ${CYAN}Simulated devices are driven by the backend simulator.${NC}"
        ;;
    emulation)
        echo -e "  ${CYAN}Start emulators separately, e.g.:${NC}"
        echo -e "  ${CYAN}  ./scripts/start-emulator.sh --emulator macos --site-id <id> --bootstrap-key <key> --device-name demo-pos-1${NC}"
        ;;
    real)
        echo -e "  ${CYAN}No devices are added by default. To add a real device:${NC}"
        echo -e "  ${CYAN}  1. Create a Site and Bootstrap key on the Dashboard${NC}"
        echo -e "  ${CYAN}  2. Pass the Site ID and Bootstrap key to the device owner${NC}"
        echo -e "  ${CYAN}  3. The owner installs the User App and registers the device${NC}"
        echo -e "  ${CYAN}  4. The device connects to this backend at: ${BACKEND_URL}${NC}"
        echo -e "  ${BLUE}Backend URL for devices: ${BACKEND_URL}${NC}"
        ;;
esac
echo ""
echo -e "${GREEN}Log Files:${NC}"
echo -e "  Backend:  $REPO_ROOT/logs/backend.log"
echo -e "  Frontend: $REPO_ROOT/logs/frontend.log"
echo ""
echo -e "${YELLOW}Quick Commands:${NC}"
echo -e "  ${CYAN}View backend logs:${NC}  tail -f $REPO_ROOT/logs/backend.log"
echo -e "  ${CYAN}View frontend logs:${NC} tail -f $REPO_ROOT/logs/frontend.log"
echo -e "  ${CYAN}Stop all services:${NC}  $REPO_ROOT/scripts/stop-dashboard.sh"
echo -e "  ${CYAN}Test API:${NC}           curl http://localhost:8000/api/v1/sites/"
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo -e "  1. Open your browser to: ${BLUE}http://localhost:5173${NC}"
echo -e "  2. You'll be redirected to login page"
echo -e "  3. Create an account using the signup form"
echo -e "  4. Login and explore the dashboard"
echo ""
echo -e "${CYAN}For detailed testing, see: docs/complete-dashboard-setup.md${NC}"
echo ""

echo -e "${YELLOW}NOTE: To restart the system cleanly:${NC}"
echo -e "  1. Stop services: ${CYAN}./scripts/stop-dashboard.sh${NC}"
echo -e "  2. Start again:   ${CYAN}./scripts/start-dashboard.sh${NC}"
echo ""

# Note: Removed automatic browser opening to eliminate terminal engagement dependency.
print_info "Dashboard is ready. Please open http://localhost:5173 manually in your browser."

exit 0
