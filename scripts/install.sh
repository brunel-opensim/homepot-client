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
DEV_INSTALL=false

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "HOMEPOT Client installation script"
    echo "Sets up Python virtual environment and installs dependencies"
    echo ""
    echo "Options:"
    echo "  --venv NAME         Virtual environment name (default: .venv)"
    echo "  --python CMD        Python command to use (default: python3)"
    echo "  --force             Force reinstall even if environment exists"
    echo "  --dev               Install development dependencies"
    echo "  --skip-tests        Skip validation tests after installation"
    echo "  -v, --verbose       Enable verbose output"
    echo "  -q, --quiet         Suppress non-essential output"
    echo "  -h, --help          Show this help message"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --venv) VENV_NAME="$2"; shift 2 ;;
        --python) PYTHON_CMD="$2"; shift 2 ;;
        --force) FORCE_REINSTALL=true; shift ;;
        --dev) DEV_INSTALL=true; shift ;;
        --skip-tests) SKIP_TESTS=true; shift ;;
        -v|--verbose) VERBOSE=true; shift ;;
        -q|--quiet) QUIET=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# Logging functions
log_info() { [[ "$QUIET" != true ]] && echo -e "${BLUE}$1${NC}"; }
log_verbose() { [[ "$VERBOSE" == true ]] && echo -e "${BLUE}[VERBOSE] $1${NC}"; }
log_success() { [[ "$QUIET" != true ]] && echo -e "${GREEN}$1${NC}"; }
log_warning() { echo -e "${YELLOW}$1${NC}"; }
log_error() { echo -e "${RED}$1${NC}"; }

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
}

# Check Python version
check_python() {
    log_info "Checking Python installation..."
    if ! command -v "$PYTHON_CMD" &> /dev/null; then
        log_error "Error: $PYTHON_CMD not found."
        exit 1
    fi

    # Check for Python 3.11+ using python itself
    if ! "$PYTHON_CMD" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
        log_error "Error: Python 3.11 or higher required."
        log_error "Found: $($PYTHON_CMD --version)"
        exit 1
    fi
    log_success "$($PYTHON_CMD --version) (compatible)"
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

    local install_target="backend/"
    local pip_flags=("-e")
    
    if [[ "$DEV_INSTALL" == true ]]; then
        install_target="backend/[dev]"
        log_info "Installing development dependencies..."
    else
        log_info "Installing production dependencies..."
    fi

    [[ "$QUIET" == true ]] && pip_flags+=("-q")

    # Install main target
    if pip install "${pip_flags[@]}" "$install_target"; then
        log_success "Dependencies installed"
    else
        log_error "Failed to install dependencies"
        return 1
    fi

    # Optional requirements.txt
    if [[ -f "backend/requirements.txt" ]]; then
        log_verbose "Installing from backend/requirements.txt"
        pip install -r backend/requirements.txt > /dev/null 2>&1 || log_warning "Some additional requirements failed"
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

run_tests() {
    if [[ "$SKIP_TESTS" == true ]]; then
        log_verbose "Skipping tests"
        return 0
    fi
    
    log_info "Running validation tests..."
    
    # Simple CLI checks
    homepot-client info > /dev/null 2>&1 || log_warning "Info command failed"
    homepot-client --help > /dev/null 2>&1 || log_warning "Help command failed"

    # Unit tests if pytest available
    if command -v pytest &> /dev/null && [[ -d "backend/tests/" ]]; then
        log_verbose "Running pytest..."
        if pytest backend/tests/ -q; then
             log_success "Unit tests passed"
        else
             log_warning "Some unit tests failed"
        fi
    else
        log_verbose "Skipping unit tests (pytest not found or no tests dir)"
    fi
}

generate_activation_script() {
    local activate_script="scripts/activate-homepot.sh"
    cat > "$activate_script" << EOF
#!/bin/bash
# Generated by install.sh on $(date)
if [[ -f "$PWD/$VENV_NAME/bin/activate" ]]; then
    source "$PWD/$VENV_NAME/bin/activate"
    echo -e "\033[0;32mHOMEPOT Client environment activated\033[0m"
else
    echo -e "\033[0;31mError: Virtual environment not found at $PWD/$VENV_NAME\033[0m"
    exit 1
fi
EOF
    chmod +x "$activate_script"
    log_success "Activation script updated: $activate_script"
}

show_next_steps() {
    [[ "$QUIET" == true ]] && return
    echo ""
    echo -e "${GREEN}Installation Success!${NC}"
    echo "1. Activate: ${YELLOW}source $VENV_NAME/bin/activate${NC}"
    echo "2. Usage:    ${YELLOW}homepot-client --help${NC}"
}

main() {
    [[ "$QUIET" != true ]] && echo -e "${GREEN}HOMEPOT Client Installer${NC}"
    check_project_root
    check_python
    setup_venv
    install_dependencies
    verify_installation
    run_tests
    generate_activation_script
    show_next_steps
}

main
