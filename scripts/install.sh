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
    echo "Examples:"
    echo "  $0                                   # Basic installation"
    echo "  $0 --dev                             # Install with development dependencies"
    echo "  $0 --venv myenv --python python3.11  # Custom environment"
    echo "  $0 --force                           # Force reinstall"
    echo "  $0 --quiet                           # Minimal output"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --venv)
            VENV_NAME="$2"
            shift 2
            ;;
        --python)
            PYTHON_CMD="$2"
            shift 2
            ;;
        --force)
            FORCE_REINSTALL=true
            shift
            ;;
        --dev)
            DEV_INSTALL=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -q|--quiet)
            QUIET=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    if [[ "$QUIET" != true ]]; then
        echo -e "${BLUE}$1${NC}"
    fi
}

log_verbose() {
    if [[ "$VERBOSE" == true ]]; then
        echo -e "${BLUE}[VERBOSE] $1${NC}"
    fi
}

log_success() {
    if [[ "$QUIET" != true ]]; then
        echo -e "${GREEN}$1${NC}"
    fi
}

log_warning() {
    echo -e "${YELLOW}$1${NC}"
}

log_error() {
    echo -e "${RED}$1${NC}"
}

# Check if we're in the right directory
check_project_root() {
    # Check for monorepo structure (backend/pyproject.toml)
    if [[ ! -f "backend/pyproject.toml" ]]; then
        log_error "Error: Not in a HOMEPOT client project directory"
        log_error "Please run this script from the HOMEPOT client project root"
        log_error "Expected to find: backend/pyproject.toml"
        exit 1
    fi
    
    if [[ ! -f "backend/src/homepot/__init__.py" ]]; then
        log_error "Error: HOMEPOT client source not found"
        log_error "Please ensure you're in the correct project directory"
        exit 1
    fi
    
    log_verbose "Project root validation passed (monorepo structure detected)"
}

# Check Python version
check_python() {
    log_info "Checking Python installation..."
    
    if ! command -v "$PYTHON_CMD" &> /dev/null; then
        log_error "Error: $PYTHON_CMD not found"
        log_error "Please install Python 3.9 or higher"
        exit 1
    fi
    
    # Get Python version
    local python_version=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    local major_version=$(echo "$python_version" | cut -d'.' -f1)
    local minor_version=$(echo "$python_version" | cut -d'.' -f2)
    
    log_verbose "Found Python $python_version"
    
    # Check minimum version (3.9)
    if [[ $major_version -lt 3 ]] || [[ $major_version -eq 3 && $minor_version -lt 9 ]]; then
        log_error "Error: Python 3.9 or higher required"
        log_error "Found: Python $python_version"
        exit 1
    fi
    
    log_success "Python $python_version (compatible)"
}

# Check if virtual environment exists
check_existing_venv() {
    if [[ -d "$VENV_NAME" ]]; then
        if [[ "$FORCE_REINSTALL" == true ]]; then
            log_warning "Removing existing virtual environment: $VENV_NAME"
            rm -rf "$VENV_NAME"
            
            log_info "Cleaning up cache files..."
            find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
            find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
            find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
            find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
            log_success "Cleanup complete"
        else
            log_warning "Virtual environment '$VENV_NAME' already exists"
            echo -e "${YELLOW}Use --force to reinstall or choose a different name with --venv${NC}"
            exit 1
        fi
    fi
}

# Create virtual environment
create_venv() {
    log_info "Creating virtual environment: $VENV_NAME"
    
    if $PYTHON_CMD -m venv "$VENV_NAME"; then
        log_success "Virtual environment created"
        log_verbose "Virtual environment path: $(pwd)/$VENV_NAME"
    else
        log_error "Failed to create virtual environment"
        exit 1
    fi
}

# Activate virtual environment
activate_venv() {
    log_verbose "Activating virtual environment"
    
    if [[ ! -f "$VENV_NAME/bin/activate" ]]; then
        log_error "Virtual environment activation script not found"
        exit 1
    fi
    
    # Source the activation script
    source "$VENV_NAME/bin/activate"
    log_verbose "Virtual environment activated"
}

# Upgrade pip
upgrade_pip() {
    log_info "Upgrading pip..."
    
    if python -m pip install --upgrade pip > /dev/null 2>&1; then
        local pip_version=$(python -m pip --version | cut -d' ' -f2)
        log_success "pip upgraded to version $pip_version"
    else
        log_warning "Failed to upgrade pip, continuing..."
    fi
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."
    
    # Install main dependencies from backend directory
    if [[ "$DEV_INSTALL" == true ]]; then
        log_verbose "Installing with development dependencies (from backend/)"
        log_info "Installing HOMEPOT client with development dependencies..."
        echo ""
        
        if [[ "$QUIET" == true ]]; then
            # Quiet mode - suppress pip output
            if python -m pip install -e "backend/[dev]" > /dev/null 2>&1; then
                log_success "Development dependencies installed"
            else
                log_error "Failed to install development dependencies"
                return 1
            fi
        else
            # Show pip output to user
            if python -m pip install -e "backend/[dev]"; then
                echo ""
                log_success "Development dependencies installed"
            else
                echo ""
                log_error "Failed to install development dependencies"
                return 1
            fi
        fi
    else
        log_verbose "Installing production dependencies (from backend/)"
        log_info "Installing HOMEPOT client..."
        echo ""
        
        if [[ "$QUIET" == true ]]; then
            # Quiet mode - suppress pip output
            if python -m pip install -e backend/ > /dev/null 2>&1; then
                log_success "Production dependencies installed"
            else
                log_error "Failed to install production dependencies"
                return 1
            fi
        else
            # Show pip output to user
            if python -m pip install -e backend/; then
                echo ""
                log_success "Production dependencies installed"
            else
                echo ""
                log_error "Failed to install production dependencies"
                return 1
            fi
        fi
    fi
    
    # Install from backend/requirements.txt if it exists
    if [[ -f "backend/requirements.txt" ]]; then
        log_verbose "Installing from backend/requirements.txt"
        log_info "Installing additional requirements..."
        echo ""
        
        if [[ "$QUIET" == true ]]; then
            # Quiet mode - suppress pip output
            if python -m pip install -r backend/requirements.txt > /dev/null 2>&1; then
                log_verbose "Additional requirements installed"
            else
                log_warning "Some requirements from backend/requirements.txt failed to install"
            fi
        else
            # Show pip output to user
            if python -m pip install -r backend/requirements.txt; then
                echo ""
                log_verbose "Additional requirements installed"
            else
                echo ""
                log_warning "Some requirements from backend/requirements.txt failed to install"
            fi
        fi
    fi
    
    return 0
}

# Verify installation
verify_installation() {
    log_info "Verifying installation..."
    
    # Test import
    if python -c "import homepot" 2>/dev/null; then
        log_success "HOMEPOT client import successful"
    else
        log_error "Failed to import HOMEPOT client"
        return 1
    fi
    
    # Test CLI command availability
    if command -v homepot-client > /dev/null 2>&1; then
        log_success "CLI command available"
        
        # Test version subcommand
        if homepot-client version > /dev/null 2>&1; then
            log_success "Version command working"
            
            # Show version in verbose mode
            if [[ "$VERBOSE" == true ]]; then
                echo -e "${GREEN}Version output:${NC}"
                homepot-client version
            fi
        else
            log_warning "Version command failed"
        fi
    else
        log_error "CLI command not available"
        return 1
    fi
    
    return 0
}

# Run basic tests
run_tests() {
    if [[ "$SKIP_TESTS" == true ]]; then
        log_verbose "Skipping tests as requested"
        return 0
    fi
    
    log_info "Running basic validation tests..."
    
    # Test version command
    if homepot-client version > /dev/null 2>&1; then
        log_success "Version command working"
    else
        log_warning "Version command failed"
    fi
    
    # Test info command
    if homepot-client info > /dev/null 2>&1; then
        log_success "Info command working"
    else
        log_warning "Info command failed"
    fi
    
    # Test help command
    if homepot-client --help > /dev/null 2>&1; then
        log_success "Help command working"
    else
        log_warning "Help command failed"
    fi
    
    # Run unit tests if pytest is available
    if command -v pytest &> /dev/null && [[ -d "backend/tests/" ]]; then
        log_verbose "Running unit tests with pytest (from backend/tests/)"
        if pytest backend/tests/ -q > /dev/null 2>&1; then
            log_success "Unit tests passed"
        else
            log_warning "Some unit tests failed"
        fi
    else
        log_verbose "Pytest not available or no backend/tests/ directory, skipping unit tests"
    fi
    
    return 0
}

# Generate activation script
generate_activation_script() {
    local activate_script="scripts/activate-homepot.sh"
    
    cat > "$activate_script" << EOF
#!/bin/bash
# HOMEPOT Client Environment Activation Script
# Generated by install.sh on $(date)

if [[ -f "$VENV_NAME/bin/activate" ]]; then
    source "$VENV_NAME/bin/activate"
    echo -e "\033[0;32mHOMEPOT Client environment activated\033[0m"
    echo "Virtual environment: $VENV_NAME"
    echo "Python: \$(python --version)"
    echo ""
    echo "Available commands:"
    echo "  homepot-client version      # Show version"
    echo "  homepot-client info         # Show client info"
    echo "  homepot-client --help       # Show help"
    echo ""
    echo "To deactivate: deactivate"
else
    echo -e "\033[0;31mError: Virtual environment not found\033[0m"
    echo "Please run scripts/install.sh first"
    exit 1
fi
EOF
    
    chmod +x "$activate_script"
    log_success "✓ Activation script created: $activate_script"
}

# Show next steps
show_next_steps() {
    if [[ "$QUIET" == true ]]; then
        return 0
    fi
    
    echo ""
    echo -e "${GREEN}Installation completed successfully!${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Activate the environment:"
    echo -e "   ${YELLOW}source $VENV_NAME/bin/activate${NC}"
    echo "   or"
    echo -e "   ${YELLOW}. ./scripts/activate-homepot.sh${NC}"
    echo "   (Note: You must use 'source' or '.' to activate in the current terminal)"
    echo ""
    echo "2. Try the HOMEPOT client:"
    echo -e "   ${YELLOW}homepot-client version${NC}"
    echo -e "   ${YELLOW}homepot-client info${NC}"
    echo -e "   ${YELLOW}homepot-client --help${NC}"
    echo ""
    echo "3. Start developing:"
    echo -e "   ${YELLOW}homepot-client --help${NC}"
    echo ""
    if [[ "$DEV_INSTALL" == true ]]; then
        echo "Development tools available:"
        echo -e "   ${YELLOW}./scripts/validate-workflows.sh${NC}  # Run validation"
        echo -e "   ${YELLOW}./scripts/test-docker.sh${NC}         # Test Docker setup"
        echo -e "   ${YELLOW}./scripts/build-docs.sh${NC}          # Build documentation"
        echo ""
    fi
    echo -e "To deactivate the environment later: ${YELLOW}deactivate${NC}"
}

# Main execution
main() {
    # Print header
    if [[ "$QUIET" != true ]]; then
        echo -e "${GREEN}HOMEPOT Client Installation${NC}"
        echo "============================"
        echo ""
    fi
    
    # Show configuration in verbose mode
    if [[ "$VERBOSE" == true ]]; then
        echo -e "${BLUE}Configuration:${NC}"
        echo "  Virtual environment: $VENV_NAME"
        echo "  Python command: $PYTHON_CMD"
        echo "  Development install: $DEV_INSTALL"
        echo "  Force reinstall: $FORCE_REINSTALL"
        echo "  Skip tests: $SKIP_TESTS"
        echo ""
    fi
    
    # Run installation steps
    check_project_root
    check_python
    check_existing_venv
    create_venv
    activate_venv
    upgrade_pip
    
    if ! install_dependencies; then
        log_error "Installation failed during dependency installation"
        exit 1
    fi
    
    if ! verify_installation; then
        log_error "Installation failed during verification"
        exit 1
    fi
    
    run_tests
    generate_activation_script
    show_next_steps
    
    log_success "Installation completed successfully!"
}

# Run main function
main
