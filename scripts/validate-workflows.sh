#!/bin/bash
# GitHub Actions Workflow Validator
# Validates workflow syntax and runs code quality checks

# Useful command
# ./scripts/validate-workflows.sh --help

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
VERBOSE=false
QUIET=false
CHECK_YAML=true
CHECK_STRUCTURE=true
CHECK_CODE=true
CHECK_PYTHON=true
CHECK_DOCS=true
FAIL_FAST=false

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS] [CHECKS]"
    echo ""
    echo "GitHub Actions workflow and code quality validator"
    echo ""
    echo "Options:"
    echo "  -v, --verbose       Enable verbose output"
    echo "  -q, --quiet         Suppress non-essential output"
    echo "  --fail-fast         Stop on first failure"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Check Selection (default: all):"
    echo "  --yaml-only         Only validate YAML syntax"
    echo "  --structure-only    Only validate workflow structure"
    echo "  --code-only         Only run code quality checks"
    echo "  --python-only       Only validate Python setup"
    echo "  --docs-only         Only validate documentation"
    echo "  --no-yaml           Skip YAML validation"
    echo "  --no-structure      Skip workflow structure validation"
    echo "  --no-code           Skip code quality checks"
    echo "  --no-python         Skip Python setup validation"
    echo "  --no-docs           Skip documentation validation"
    echo ""
    echo "Examples:"
    echo "  $0                          # Run all checks"
    echo "  $0 --verbose                # Run all checks with verbose output"
    echo "  $0 --code-only              # Only run code quality checks"
    echo "  $0 --no-code --no-python    # Skip code and Python checks"
    echo "  $0 --fail-fast              # Stop on first failure"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -q|--quiet)
            QUIET=true
            shift
            ;;
        --fail-fast)
            FAIL_FAST=true
            shift
            ;;
        --yaml-only)
            CHECK_YAML=true
            CHECK_STRUCTURE=false
            CHECK_CODE=false
            CHECK_PYTHON=false
            CHECK_DOCS=false
            shift
            ;;
        --structure-only)
            CHECK_YAML=false
            CHECK_STRUCTURE=true
            CHECK_CODE=false
            CHECK_PYTHON=false
            CHECK_DOCS=false
            shift
            ;;
        --code-only)
            CHECK_YAML=false
            CHECK_STRUCTURE=false
            CHECK_CODE=true
            CHECK_PYTHON=false
            CHECK_DOCS=false
            shift
            ;;
        --python-only)
            CHECK_YAML=false
            CHECK_STRUCTURE=false
            CHECK_CODE=false
            CHECK_PYTHON=true
            CHECK_DOCS=false
            shift
            ;;
        --docs-only)
            CHECK_YAML=false
            CHECK_STRUCTURE=false
            CHECK_CODE=false
            CHECK_PYTHON=false
            CHECK_DOCS=true
            shift
            ;;
        --no-yaml)
            CHECK_YAML=false
            shift
            ;;
        --no-structure)
            CHECK_STRUCTURE=false
            shift
            ;;
        --no-code)
            CHECK_CODE=false
            shift
            ;;
        --no-python)
            CHECK_PYTHON=false
            shift
            ;;
        --no-docs)
            CHECK_DOCS=false
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

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0

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
    echo -e "${GREEN}$1${NC}"
}

log_warning() {
    echo -e "${YELLOW}$1${NC}"
}

log_error() {
    echo -e "${RED}$1${NC}"
}

# Function to run a check
run_check() {
    local check_name="$1"
    local check_command="$2"
    
    if [[ "$QUIET" != true ]]; then
        echo -e "\n$check_name"
        echo "----------------------------------------"
    fi
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    log_verbose "Running: $check_command"
    
    if eval "$check_command"; then
        log_success "$check_name: PASSED"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        log_error "$check_name: FAILED"
        if [[ "$FAIL_FAST" == true ]]; then
            echo -e "\n${RED}Stopping due to --fail-fast option${NC}"
            exit 1
        fi
        return 1
    fi
}

# 1. Validate YAML syntax
validate_yaml() {
    local files_found=false
    for file in .github/workflows/*.yml .github/workflows/*.yaml; do
        [ -f "$file" ] || continue
        files_found=true
        log_verbose "Validating YAML file: $file"
        echo -n "  Checking $(basename "$file"): "
        if python3 -c "import yaml; yaml.safe_load(open('$file', 'r'))" 2>/dev/null; then
            echo -e "${GREEN}Valid${NC}"
        else
            echo -e "${RED}Invalid YAML${NC}"
            log_verbose "YAML validation failed for $file"
            return 1
        fi
    done
    
    if [[ "$files_found" == false ]]; then
        log_warning "No workflow files found in .github/workflows/"
        return 1
    fi
    
    return 0
}

# 2. Basic workflow structure check
validate_structure() {
    local files_found=false
    for file in .github/workflows/*.yml .github/workflows/*.yaml; do
        [ -f "$file" ] || continue
        files_found=true
        log_verbose "Checking workflow structure: $file"
        echo -n "  Checking $(basename "$file"): "
        
        local has_name=$(grep -q "^name:" "$file" && echo true || echo false)
        local has_trigger=$(grep -q "^on:\|^true:" "$file" && echo true || echo false)
        local has_jobs=$(grep -q "^jobs:" "$file" && echo true || echo false)
        
        if [[ "$has_name" == true && "$has_trigger" == true && "$has_jobs" == true ]]; then
            echo -e "${GREEN}Valid structure${NC}"
            log_verbose "✓ name: found, ✓ trigger: found, ✓ jobs: found"
        else
            echo -e "${RED}Missing required fields${NC}"
            log_verbose "✗ name: $has_name, ✗ trigger: $has_trigger, ✗ jobs: $has_jobs"
            return 1
        fi
    done
    
    if [[ "$files_found" == false ]]; then
        log_warning "No workflow files found for structure validation"
        return 1
    fi
    
    return 0
}

# 3. Essential code quality
validate_code_quality() {
    log_info "  Running essential code quality checks..."
    
    # Check if source directories exist
    if [[ ! -d "src/" ]] && [[ ! -d "tests/" ]]; then
        log_warning "No src/ or tests/ directories found"
        return 0
    fi
    
    local failed=false
    
    # Black formatting
    if command -v black >/dev/null 2>&1; then
        echo -n "    Black formatting: "
        log_verbose "Running: black --check src/ tests/"
        if black --check src/ tests/ 2>/dev/null; then
            echo -e "${GREEN}Passed${NC}"
        else
            echo -e "${RED}Failed - run: black src/ tests/${NC}"
            failed=true
        fi
    else
        log_verbose "Black not available, skipping formatting check"
    fi
    
    # flake8 linting
    if command -v flake8 >/dev/null 2>&1; then
        echo -n "    Linting (flake8): "
        log_verbose "Running: flake8 src/ tests/"
        if flake8 src/ tests/ 2>/dev/null; then
            echo -e "${GREEN}Passed${NC}"
        else
            echo -e "${RED}Failed - run: flake8 src/ tests/${NC}"
            failed=true
        fi
    else
        log_verbose "flake8 not available, skipping linting check"
    fi
    
    if [[ "$failed" == true ]]; then
        return 1
    fi
    
    return 0
}

# 4. Basic Python setup
validate_python() {
    log_info "  Checking Python setup..."
    
    # Check pyproject.toml
    if [ -f "pyproject.toml" ]; then
        echo -n "    pyproject.toml: "
        log_verbose "Checking pyproject.toml and dependencies"
        if python -m pip check > /dev/null 2>&1; then
            echo -e "${GREEN}Valid${NC}"
        else
            echo -e "${YELLOW}Warning - dependency issues${NC}"
            log_verbose "Some dependency conflicts detected"
        fi
    else
        log_verbose "pyproject.toml not found"
    fi
    
    # Check requirements.txt
    if [ -f "requirements.txt" ]; then
        echo -n "    requirements.txt: "
        echo -e "${GREEN}Found${NC}"
        log_verbose "requirements.txt found with $(wc -l < requirements.txt) lines"
    else
        log_verbose "requirements.txt not found"
    fi
    
    # Check setup.py (legacy)
    if [ -f "setup.py" ]; then
        log_verbose "setup.py found (legacy setup)"
    fi
    
    return 0
}

# 5. Documentation validation
validate_documentation() {
    log_info "  Checking documentation files..."
    
    # Check essential documentation files
    local docs_files=("README.md" "CONTRIBUTING.md" "docs/index.md" "docs/getting-started.md")
    local failed=false
    
    for file in "${docs_files[@]}"; do
        if [ -f "$file" ]; then
            echo -n "    $file: "
            if [ -s "$file" ]; then
                echo -e "${GREEN}Found${NC}"
                log_verbose "$file found with $(wc -l < "$file") lines"
            else
                echo -e "${YELLOW}Empty${NC}"
                log_verbose "$file exists but is empty"
            fi
        else
            echo -n "    $file: "
            echo -e "${RED}Missing${NC}"
            log_verbose "$file not found"
            failed=true
        fi
    done
    
    # Check for additional documentation
    if [[ "$VERBOSE" == true ]]; then
        if [ -d "docs/" ]; then
            local doc_count=$(find docs/ -name "*.md" | wc -l)
            log_verbose "Found $doc_count markdown files in docs/ directory"
        fi
    fi
    
    if [[ "$failed" == true ]]; then
        return 1
    fi
    
    return 0
}

# Main execution
main() {
    # Print header unless quiet mode
    if [[ "$QUIET" != true ]]; then
        echo -e "${GREEN}HOMEPOT Workflow & Code Quality Validation${NC}"
        echo "============================================"
        
        # Show enabled checks
        local enabled_checks=()
        [[ "$CHECK_YAML" == true ]] && enabled_checks+=("YAML")
        [[ "$CHECK_STRUCTURE" == true ]] && enabled_checks+=("Structure")
        [[ "$CHECK_CODE" == true ]] && enabled_checks+=("Code Quality")
        [[ "$CHECK_PYTHON" == true ]] && enabled_checks+=("Python Setup")
        [[ "$CHECK_DOCS" == true ]] && enabled_checks+=("Documentation")
        
        if [[ ${#enabled_checks[@]} -eq 5 ]]; then
            echo "Running all validation checks..."
        else
            echo "Running selected checks: ${enabled_checks[*]}"
        fi
        
        if [[ "$VERBOSE" == true ]]; then
            echo -e "${BLUE}Verbose mode enabled${NC}"
        fi
        
        if [[ "$FAIL_FAST" == true ]]; then
            echo -e "${YELLOW}Fail-fast mode enabled${NC}"
        fi
    fi
    
    # Check if we're in the right directory
    if [[ ! -f "pyproject.toml" ]] && [[ ! -f "setup.py" ]] && [[ ! -f "requirements.txt" ]]; then
        log_error "Error: No Python project files found. Please run from project root."
        exit 1
    fi
    
    # Run selected checks
    [[ "$CHECK_YAML" == true ]] && run_check "YAML Syntax" "validate_yaml"
    [[ "$CHECK_STRUCTURE" == true ]] && run_check "Workflow Structure" "validate_structure"
    [[ "$CHECK_CODE" == true ]] && run_check "Code Quality" "validate_code_quality"
    [[ "$CHECK_PYTHON" == true ]] && run_check "Python Setup" "validate_python"
    [[ "$CHECK_DOCS" == true ]] && run_check "Documentation" "validate_documentation"
    
    # Final summary (unless quiet)
    if [[ "$QUIET" != true ]]; then
        echo -e "\nValidation Summary"
        echo "====================================="
        echo "Total checks: $TOTAL_CHECKS"
        echo "Passed: $PASSED_CHECKS"
        echo "Failed: $((TOTAL_CHECKS - PASSED_CHECKS))"
    fi
    
    if [ $PASSED_CHECKS -eq $TOTAL_CHECKS ]; then
        if [[ "$QUIET" != true ]]; then
            echo -e "\n${GREEN}All checks passed!${NC}"
            echo -e "${GREEN}Repository is ready for development.${NC}"
        fi
        exit 0
    else
        if [[ "$QUIET" != true ]]; then
            echo -e "\n${RED}Some checks failed.${NC}"
            echo -e "${YELLOW}Fix the issues above before pushing.${NC}"
        fi
        exit 1
    fi
}

# Run main function
main
