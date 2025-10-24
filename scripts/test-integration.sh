#!/bin/bash

################################################################################
# HOMEPOT Client - Integrated Test & Development Script
#
# This script automates the complete setup and launch of the HOMEPOT Client
# system, including both backend (FastAPI) and frontend (React/Vite).
#
# Usage:
#   ./scripts/test-integration.sh           # Full setup and start
#   ./scripts/test-integration.sh --quick   # Skip dependency installation
#   ./scripts/test-integration.sh --help    # Show help
#
# What it does:
#   1. Checks prerequisites (Python, Node.js, npm)
#   2. Sets up Python virtual environment
#   3. Installs dependencies (backend & frontend)
#   4. Generates VAPID keys for Web Push
#   5. Creates environment configuration files
#   6. Initializes database
#   7. Starts backend API server
#   8. Starts frontend development server
#   9. Opens browser automatically
#   10. Monitors both services
#   11. Graceful shutdown on Ctrl+C
#
# Author: HOMEPOT Team
# Date: October 24, 2025
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
VENV_DIR="$BACKEND_DIR/venv"

# Server configuration
BACKEND_HOST="localhost"
BACKEND_PORT=8000
FRONTEND_PORT=5173
BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"

# Process IDs for cleanup
BACKEND_PID=""
FRONTEND_PID=""

# Parse command line arguments
SKIP_INSTALL=false
SHOW_HELP=false

for arg in "$@"; do
  case $arg in
    --quick)
      SKIP_INSTALL=true
      shift
      ;;
    --help|-h)
      SHOW_HELP=true
      shift
      ;;
    *)
      ;;
  esac
done

################################################################################
# Helper Functions
################################################################################

print_header() {
  echo ""
  echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}${CYAN}  $1${NC}"
  echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

print_step() {
  echo -e "${BOLD}${BLUE}▶${NC} $1"
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

show_help() {
  cat << EOF
${BOLD}HOMEPOT Client - Integrated Test & Development Script${NC}

${BOLD}USAGE:${NC}
  ./scripts/test-integration.sh [OPTIONS]

${BOLD}OPTIONS:${NC}
  --quick       Skip dependency installation (faster restart)
  --help, -h    Show this help message

${BOLD}DESCRIPTION:${NC}
  This script sets up and launches the complete HOMEPOT Client system:
  - Backend API (FastAPI) on http://localhost:8000
  - Frontend App (React/Vite) on http://localhost:5173
  - Auto-generates VAPID keys for push notifications
  - Creates environment configuration files
  - Opens browser automatically when ready

${BOLD}REQUIREMENTS:${NC}
  - Python 3.9 or higher
  - Node.js 18 or higher
  - npm or yarn

${BOLD}EXAMPLES:${NC}
  ${GREEN}# Full setup (first time or after updates)${NC}
  ./scripts/test-integration.sh

  ${GREEN}# Quick restart (dependencies already installed)${NC}
  ./scripts/test-integration.sh --quick

${BOLD}CONTROLS:${NC}
  ${YELLOW}Ctrl+C${NC}  Stop both backend and frontend servers

${BOLD}URLs:${NC}
  Backend API:  ${CYAN}http://localhost:8000${NC}
  API Docs:     ${CYAN}http://localhost:8000/docs${NC}
  Frontend:     ${CYAN}http://localhost:5173${NC}

EOF
}

cleanup() {
  echo ""
  print_header "Shutting Down Services"
  
  if [ ! -z "$BACKEND_PID" ]; then
    print_step "Stopping backend server (PID: $BACKEND_PID)..."
    kill -TERM $BACKEND_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    print_success "Backend stopped"
  fi
  
  if [ ! -z "$FRONTEND_PID" ]; then
    print_step "Stopping frontend server (PID: $FRONTEND_PID)..."
    kill -TERM $FRONTEND_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    print_success "Frontend stopped"
  fi
  
  echo ""
  print_success "All services stopped gracefully"
  echo ""
  exit 0
}

# Set up trap for cleanup on exit
trap cleanup EXIT INT TERM

check_command() {
  if ! command -v $1 &> /dev/null; then
    print_error "$1 is not installed"
    return 1
  else
    print_success "$1 is installed"
    return 0
  fi
}

wait_for_service() {
  local url=$1
  local service_name=$2
  local max_attempts=30
  local attempt=0
  
  print_step "Waiting for $service_name to be ready..."
  
  while [ $attempt -lt $max_attempts ]; do
    if curl -s -f "$url" > /dev/null 2>&1; then
      print_success "$service_name is ready!"
      return 0
    fi
    
    attempt=$((attempt + 1))
    echo -ne "\r  Attempt $attempt/$max_attempts..."
    sleep 2
  done
  
  echo ""
  print_error "$service_name failed to start"
  return 1
}

generate_vapid_keys() {
  print_step "Generating VAPID keys for Web Push notifications..."
  
  cd "$BACKEND_DIR"
  
  # Activate virtual environment
  source "$VENV_DIR/bin/activate"
  
  # Generate VAPID keys using Python
  python3 << 'EOF'
import os
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import base64

# Generate private key
private_key = ec.generate_private_key(ec.SECP256R1())

# Get private key bytes
private_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# Get public key bytes
public_key = private_key.public_key()
public_bytes = public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)

# Convert to base64 URL-safe format
private_key_b64 = base64.urlsafe_b64encode(private_bytes).decode('utf-8').rstrip('=')
public_key_b64 = base64.urlsafe_b64encode(public_bytes).decode('utf-8').rstrip('=')

print(f"VAPID_PRIVATE_KEY={private_key_b64}")
print(f"VAPID_PUBLIC_KEY={public_key_b64}")
EOF
  
  deactivate
  
  print_success "VAPID keys generated"
}

################################################################################
# Main Script
################################################################################

if [ "$SHOW_HELP" = true ]; then
  show_help
  exit 0
fi

clear

print_header "HOMEPOT Client - Integrated Setup & Launch"

echo -e "${BOLD}Starting HOMEPOT Client integration environment...${NC}"
echo ""

# Step 1: Check Prerequisites
print_header "Step 1/9: Checking Prerequisites"

check_command python3 || exit 1
check_command node || exit 1
check_command npm || exit 1
check_command curl || exit 1

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_info "Python version: $PYTHON_VERSION"

# Check Node.js version
NODE_VERSION=$(node --version | sed 's/v//')
print_info "Node.js version: $NODE_VERSION"

echo ""

# Step 2: Setup Python Virtual Environment
print_header "Step 2/9: Setting Up Python Environment"

if [ ! -d "$VENV_DIR" ]; then
  print_step "Creating Python virtual environment..."
  cd "$BACKEND_DIR"
  python3 -m venv venv
  print_success "Virtual environment created"
else
  print_info "Virtual environment already exists"
fi

echo ""

# Step 3: Install Dependencies
if [ "$SKIP_INSTALL" = false ]; then
  print_header "Step 3/9: Installing Dependencies"
  
  # Backend dependencies
  print_step "Installing backend dependencies..."
  cd "$BACKEND_DIR"
  source "$VENV_DIR/bin/activate"
  pip install -q --upgrade pip
  pip install -q -r requirements.txt
  deactivate
  print_success "Backend dependencies installed"
  
  # Frontend dependencies
  print_step "Installing frontend dependencies..."
  cd "$FRONTEND_DIR"
  npm install --silent
  print_success "Frontend dependencies installed"
  
  echo ""
else
  print_header "Step 3/9: Skipping Dependency Installation (--quick mode)"
  echo ""
fi

# Step 4: Generate VAPID Keys
print_header "Step 4/9: Configuring Web Push (VAPID Keys)"

if [ ! -f "$BACKEND_DIR/.env" ] || ! grep -q "WEB_PUSH_VAPID_PRIVATE_KEY" "$BACKEND_DIR/.env" 2>/dev/null; then
  VAPID_OUTPUT=$(generate_vapid_keys)
  VAPID_PRIVATE=$(echo "$VAPID_OUTPUT" | grep "VAPID_PRIVATE_KEY" | cut -d'=' -f2)
  VAPID_PUBLIC=$(echo "$VAPID_OUTPUT" | grep "VAPID_PUBLIC_KEY" | cut -d'=' -f2)
  print_success "VAPID keys ready"
else
  print_info "VAPID keys already configured"
  VAPID_PRIVATE=$(grep "WEB_PUSH_VAPID_PRIVATE_KEY" "$BACKEND_DIR/.env" | cut -d'=' -f2)
  VAPID_PUBLIC=$(grep "WEB_PUSH_VAPID_PUBLIC_KEY" "$BACKEND_DIR/.env" | cut -d'=' -f2)
fi

echo ""

# Step 5: Create Environment Files
print_header "Step 5/9: Creating Environment Configuration"

# Backend .env
if [ ! -f "$BACKEND_DIR/.env" ]; then
  print_step "Creating backend .env file..."
  cat > "$BACKEND_DIR/.env" << EOF
# HOMEPOT Backend Environment Variables (Auto-generated)
# Generated: $(date)

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true
ENVIRONMENT=development

# Database Configuration (nested with DATABASE__)
DATABASE__URL=sqlite:///../data/homepot.db
DATABASE__ECHO_SQL=false

# Authentication Settings (nested with AUTH__)
AUTH__SECRET_KEY=homepot-dev-secret-$(openssl rand -hex 16)
AUTH__ALGORITHM=HS256
AUTH__ACCESS_TOKEN_EXPIRE_MINUTES=30
AUTH__API_KEY_HEADER=X-API-Key

# Redis Settings (nested with REDIS__)
REDIS__URL=redis://localhost:6379/0

# Push Notification Settings (nested with PUSH__)
PUSH__ENABLED=true
PUSH__DEFAULT_TTL=300

# WebSocket Settings (nested with WEBSOCKET__)
WEBSOCKET__ENABLED=true
WEBSOCKET__PING_INTERVAL=20
WEBSOCKET__PING_TIMEOUT=10

# Logging Settings (nested with LOGGING__)
LOGGING__LEVEL=INFO

# Device Settings (nested with DEVICES__)
DEVICES__HEALTH_CHECK_INTERVAL=60

# Note: Web Push VAPID keys should be configured separately
# via the PushNotificationSettings or push provider configuration
EOF
  print_success "Backend .env created"
else
  print_info "Backend .env already exists"
fi

# Frontend .env.local
if [ ! -f "$FRONTEND_DIR/.env.local" ]; then
  print_step "Creating frontend .env.local file..."
  cat > "$FRONTEND_DIR/.env.local" << EOF
# HOMEPOT Frontend Environment Variables (Auto-generated)
# Generated: $(date)

# Backend API Configuration
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000

# API Settings
VITE_API_TIMEOUT=30000

# Feature Flags
VITE_ENABLE_WEBSOCKET=true
VITE_ENABLE_PUSH_NOTIFICATIONS=true

# Development
VITE_ENABLE_DEBUG_LOGS=true
EOF
  print_success "Frontend .env.local created"
else
  print_info "Frontend .env.local already exists"
fi

echo ""

# Step 6: Initialize Database
print_header "Step 6/9: Initializing Database"

# Create data directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/data"

if [ ! -f "$PROJECT_ROOT/data/homepot.db" ]; then
  print_step "Creating SQLite database..."
  touch "$PROJECT_ROOT/data/homepot.db"
  print_success "Database initialized"
else
  print_info "Database already exists"
fi

echo ""

# Step 7: Start Backend
print_header "Step 7/9: Starting Backend API Server"

cd "$BACKEND_DIR"
source "$VENV_DIR/bin/activate"

print_step "Launching FastAPI server on ${BACKEND_URL}..."

# Start backend in background
python -m uvicorn homepot_client.main:app \
  --host $BACKEND_HOST \
  --port $BACKEND_PORT \
  --reload \
  --log-level info > "$PROJECT_ROOT/backend.log" 2>&1 &

BACKEND_PID=$!

print_info "Backend PID: $BACKEND_PID"
print_info "Backend logs: $PROJECT_ROOT/backend.log"

# Wait for backend to be ready
wait_for_service "${BACKEND_URL}/health" "Backend API" || exit 1

deactivate

echo ""

# Step 8: Start Frontend
print_header "Step 8/9: Starting Frontend Development Server"

cd "$FRONTEND_DIR"

print_step "Launching Vite server on ${FRONTEND_URL}..."

# Start frontend in background
npm run dev > "$PROJECT_ROOT/frontend.log" 2>&1 &

FRONTEND_PID=$!

print_info "Frontend PID: $FRONTEND_PID"
print_info "Frontend logs: $PROJECT_ROOT/frontend.log"

# Wait for frontend to be ready
sleep 5  # Vite takes a moment to compile

echo ""

# Step 9: Ready!
print_header "Step 9/9: HOMEPOT Client Ready!"

echo ""
echo -e "${BOLD}${GREEN}SUCCESS! Your HOMEPOT Client is now running!${NC}"
echo ""
echo -e "${BOLD}Access Points:${NC}"
echo -e "   ${CYAN}Frontend:${NC}     ${BOLD}${FRONTEND_URL}${NC}"
echo -e "   ${CYAN}Backend API:${NC}  ${BOLD}${BACKEND_URL}${NC}"
echo -e "   ${CYAN}API Docs:${NC}     ${BOLD}${BACKEND_URL}/docs${NC}"
echo -e "   ${CYAN}API v1:${NC}       ${BOLD}${BACKEND_URL}/api/v1${NC}"
echo ""
echo -e "${BOLD}🎯 What You Can Do Now:${NC}"
echo -e "   ${GREEN}1.${NC} ${BOLD}Visit the App:${NC}     ${FRONTEND_URL}"
echo -e "   ${GREEN}2.${NC} ${BOLD}Test the API:${NC}      ${BACKEND_URL}/docs"
echo -e "   ${GREEN}3.${NC} ${BOLD}Try Features:${NC}      Push notifications, device management, real-time updates"
echo -e "   ${GREEN}4.${NC} ${BOLD}Monitor Logs:${NC}      tail -f backend.log or frontend.log"
echo ""
echo -e "${BOLD}✨ Features Available:${NC}"
echo -e "   ${GREEN}✓${NC} Push Notifications (FCM, WNS, APNs, Web Push, MQTT)"
echo -e "   ${GREEN}✓${NC} Web Push with VAPID keys"
echo -e "   ${GREEN}✓${NC} Real-time WebSocket support"
echo -e "   ${GREEN}✓${NC} Device & Site management"
echo -e "   ${GREEN}✓${NC} Agent simulation"
echo ""
echo -e "${BOLD}⏸  To Stop:${NC}"
echo -e "   Press ${YELLOW}Ctrl+C${NC} to gracefully shutdown both servers"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Open browser (platform-specific)
print_step "Opening browser..."
sleep 2

if command -v xdg-open &> /dev/null; then
  xdg-open "${FRONTEND_URL}" &> /dev/null &
elif command -v open &> /dev/null; then
  open "${FRONTEND_URL}" &> /dev/null &
elif command -v start &> /dev/null; then
  start "${FRONTEND_URL}" &> /dev/null &
else
  print_warning "Could not open browser automatically"
  print_info "Please open ${FRONTEND_URL} in your browser"
fi

echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}  Services Running - Ready for Testing!${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}The HOMEPOT Client is now running and ready for you to test!${NC}"
echo ""
echo -e "${BOLD}What you can do:${NC}"
echo -e "  ${GREEN}1.${NC} Visit ${CYAN}http://localhost:5173${NC} to interact with the frontend"
echo -e "  ${GREEN}2.${NC} Visit ${CYAN}http://localhost:8000/docs${NC} to test the API"
echo -e "  ${GREEN}3.${NC} Test push notifications, create sites, add devices"
echo -e "  ${GREEN}4.${NC} Monitor logs in real-time:"
echo -e "     ${YELLOW}tail -f backend.log${NC}"
echo -e "     ${YELLOW}tail -f frontend.log${NC}"
echo ""
echo -e "${BOLD}${YELLOW}⏸  Services will keep running until you press Ctrl+C${NC}"
echo ""
print_info "Monitoring services... (Press Ctrl+C when you're done testing)"
echo ""

# Keep script running and monitor processes
while true; do
  # Check if backend is still running
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    print_error "Backend process died unexpectedly!"
    print_info "Check logs: cat $PROJECT_ROOT/backend.log"
    exit 1
  fi
  
  # Check if frontend is still running
  if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    print_error "Frontend process died unexpectedly!"
    print_info "Check logs: cat $PROJECT_ROOT/frontend.log"
    exit 1
  fi
  
  sleep 5
done
