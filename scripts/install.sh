#!/bin/bash
# HOMEPOT Client Installation Script
# Sets up Python virtual environment and installs dependencies

# Useful command
# ./scripts/install.sh --help

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
VENV_NAME=".venv"
PYTHON_CMD="python3"
FORCE_REINSTALL=false
SKIP_TESTS=false
VERBOSE=false
QUIET=false

# Print usage
usage() {
    echo "HOMEPOT Client Installer"
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Common Options:"
    echo "  --force             Force reinstall (cleans existing environment)"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Advanced Options:"
    echo "  --venv NAME         Set virtual environment name (default: .venv)"
    echo "  --python CMD        Specify Python command (default: auto-detect)"
    echo "  --skip-tests        Skip post-install validation"
    echo "  -v, --verbose       Enable verbose debugging output"
    echo "  -q, --quiet         Suppress output (useful for scripts)"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --venv) VENV_NAME="$2"; shift 2 ;;
        --python) PYTHON_CMD="$2"; shift 2 ;;
        --force) FORCE_REINSTALL=true; shift ;;
        --skip-tests) SKIP_TESTS=true; shift ;;
        -v|--verbose) VERBOSE=true; shift ;;
        -q|--quiet) QUIET=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# Logging functions
log_info() { [[ "$QUIET" != true ]] && echo -e "${BLUE}$1${NC}" || true; }
log_verbose() { [[ "$VERBOSE" == true ]] && echo -e "${BLUE}[VERBOSE] $1${NC}" || true; }
log_success() { [[ "$QUIET" != true ]] && echo -e "${GREEN}$1${NC}" || true; }
log_warning() { echo -e "${YELLOW}$1${NC}" || true; }
log_error() { echo -e "${RED}$1${NC}" || true; }

# Cleanup on error
cleanup_on_error() {
    log_error "Installation failed!"
}
trap 'if [[ $? -ne 0 ]]; then cleanup_on_error; fi' EXIT

# Check if we're in the right directory
check_project_root() {
    if [[ ! -f "backend/pyproject.toml" ]]; then
        log_error "Error: Not in a HOMEPOT client project directory"
        log_error "Expected to find: backend/pyproject.toml"
        exit 1
    fi
    log_verbose "Project root validation passed"
    return 0
}

# Check Python version
check_python() {
    log_info "Checking Python installation..."
    
    # If user didn't specify a command, try to find the best one
    if [[ "$PYTHON_CMD" == "python3" ]]; then
        # List of candidates to try in order
        local candidates=("python3.12" "python3.11" "python3")
        for cmd in "${candidates[@]}"; do
            if command -v "$cmd" &> /dev/null; then
                # Check version compatibility
                if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
                    PYTHON_CMD="$cmd"
                    log_verbose "Auto-detected compatible Python: $PYTHON_CMD"
                    break
                fi
            fi
        done
    fi

    if ! command -v "$PYTHON_CMD" &> /dev/null; then
        log_error "Error: Python interpreter '$PYTHON_CMD' not found."
        log_error "This project requires Python 3.11 or higher."
        exit 1
    fi

    # Final verification
    if ! "$PYTHON_CMD" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
        log_error "Error: Python 3.11 or higher required."
        log_error "Current '$PYTHON_CMD' is $($PYTHON_CMD --version 2>&1)"
        log_error "Please install python3.11 or python3.12 package."
        exit 1
    fi
    log_success "Using $($PYTHON_CMD --version 2>&1) ($PYTHON_CMD)"
}

# Check/Create virtual environment
setup_venv() {
    if [[ -d "$VENV_NAME" ]]; then
        if [[ "$FORCE_REINSTALL" == true ]]; then
            log_warning "Removing existing virtual environment: $VENV_NAME"
            rm -rf "$VENV_NAME"
            # Cleanup caches
            find . -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name "*.egg-info" \) -exec rm -rf {} + 2>/dev/null || true
        else
            log_warning "Virtual environment '$VENV_NAME' already exists. Use --force to reinstall."
            return 0
        fi
    fi
    
    log_info "Creating virtual environment: $VENV_NAME"
    if ! "$PYTHON_CMD" -m venv "$VENV_NAME"; then
        log_error "Failed to create virtual environment"
        exit 1
    fi
    log_success "Virtual environment created"
}

# Install dependencies
install_dependencies() {
    # Activate venv
    source "$VENV_NAME/bin/activate"
    
    log_info "Upgrading pip..."
    pip install --upgrade pip > /dev/null 2>&1 || log_warning "Failed to upgrade pip"

    local pip_flags=("-e")
    [[ "$QUIET" == true ]] && pip_flags+=("-q")

    log_info "Installing dependencies..."

    # Install project in editable mode
    if pip install "${pip_flags[@]}" "backend/"; then
        log_verbose "Project installed successfully"
    else
        log_error "Failed to install project"
        return 1
    fi

    # Install pinned requirements
    if [[ -f "backend/requirements.txt" ]]; then
        log_verbose "Installing from backend/requirements.txt"
        pip install -r backend/requirements.txt > /dev/null 2>&1 || log_warning "Some requirements failed to install"
    else
        log_warning "backend/requirements.txt not found"
    fi
}

# Check Node.js and Install Frontend Dependencies
install_frontend() {
    log_info "Checking Node.js configuration..."
    
    if ! command -v node &> /dev/null; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            log_warning "Node.js not found. Attempting install via Homebrew..."
            if command -v brew &> /dev/null; then
                brew install node || { log_error "Failed to install Node.js"; exit 1; }
            else
                log_error "Homebrew not found. Please install Node.js manually."
                exit 1
            fi
        else
             log_error "Node.js not found. Please install Node.js (v22 recommended)."
             exit 1
        fi
    fi
    
    local node_version
    node_version=$(node --version)
    log_success "Using Node.js $node_version"

    if [[ -d "frontend" ]]; then
        log_info "Installing frontend dependencies..."
        if cd frontend && npm install; then
            log_success "Frontend dependencies installed"
            cd ..
        else
            log_error "Frontend installation failed"
            cd ..
            exit 1
        fi
    else
        log_warning "frontend/ directory not found. Skipping."
    fi
}

verify_installation() {
    log_info "Verifying installation..."
    if ! python -c "import homepot" 2>/dev/null; then
        log_error "Failed to import homepot"
        return 1
    fi
    
    if ! command -v homepot-client > /dev/null; then
        log_error "CLI command 'homepot-client' not found"
        return 1
    fi
    
    # Check version
    if ! homepot-client version > /dev/null 2>&1; then
        log_warning "Version command failed execution"
    else
        [[ "$VERBOSE" == true ]] && homepot-client version
    fi
    log_success "Verification passed"
}

show_next_steps() {
    [[ "$QUIET" == true ]] && return
    echo ""
    echo -e "${GREEN}Installation Success!${NC}"
    echo -e "1. Activate: ${YELLOW}source $VENV_NAME/bin/activate${NC}"
    echo -e "2. Usage:    ${YELLOW}homepot-client --help${NC}"
}

main() {
    [[ "$QUIET" != true ]] && echo -e "${GREEN}HOMEPOT Client Installer${NC}"
    check_project_root
    check_python
    setup_venv
    install_dependencies
    install_frontend
    verify_installation
    show_next_steps
}

main
