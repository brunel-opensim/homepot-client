#!/bin/bash
#
# POSDummy Runner - Quick verification script for HOMEPOT infrastructure
#
# This script runs the POSDummy integration test to quickly verify that
# the HOMEPOT system is functional. Inspired by FabSim3's FabDummy pattern.
#
# Usage:
#   ./scripts/run-pos-dummy.sh [--verbose] [--quick]
#   
#   --verbose: Show detailed output
#   --quick: Run only the fastest subset of tests
#

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Script configuration
VERBOSE=false
QUICK=false
START_TIME=$(date +%s)

# Function to print colored output
log_info() {
    echo -e "${BLUE}$1${NC}"
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

log_celebration() {
    echo -e "${GREEN}$1${NC}"
}

# Function to show help
show_help() {
    cat << EOF
POSDummy Runner - HOMEPOT Infrastructure Verification

Usage: $0 [OPTIONS]

Options:
    -h, --help      Show this help message
    -v, --verbose   Show detailed output
    -q, --quick     Run only quick verification checks

Examples:
    $0                      # Run full test
    $0 --quick              # Run quick checks only  
    $0 --verbose            # Run with detailed output

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -q|--quick)
                QUICK=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Function to ensure we're in the right directory
setup_environment() {
    log_info "Setting up POSDummy environment..."
    
    # Change to project root if we're in scripts directory
    if [[ "$(basename "$PWD")" == "scripts" ]]; then
        cd ..
    fi
    
    # Verify we're in the right place
    if [[ ! -d "backend/homepot_client" ]]; then
        log_error "Not in HOMEPOT project root directory"
        log_error "Run this script from the homepot-client directory"
        return 1
    fi
    
    # Check for required files
    if [[ ! -f "backend/tests/test_pos_dummy.py" ]]; then
        log_error "POSDummy test file not found: backend/tests/test_pos_dummy.py"
        return 1
    fi
    
    return 0
}

# Function to run quick POSDummy tests
run_quick_posdummy() {
    log_info "Running Quick POSDummy verification..."
    
    local test_commands=(
        "python -m pytest backend/tests/test_pos_dummy.py::TestPOSDummy::test_critical_imports -q --tb=short --no-cov"
        "python -m pytest backend/tests/test_pos_dummy.py::TestPOSDummy::test_configuration_integrity -q --tb=short --no-cov"
        "python -m pytest backend/tests/test_pos_dummy.py::TestPOSDummy::test_package_structure -q --tb=short --no-cov"
    )
    
    local i=1
    for cmd in "${test_commands[@]}"; do
        echo "  [$i/${#test_commands[@]}] Running check..."
        
        if $VERBOSE; then
            echo "    Command: $cmd"
        fi
        
        if output=$(eval "$cmd" 2>&1); then
            log_success "    Check $i passed"
            if $VERBOSE; then
                echo "$output"
            fi
        else
            log_error "    Check $i failed:"
            echo "$output"
            return 1
        fi
        
        ((i++))
    done
    
    return 0
}

# Function to run full POSDummy test suite
run_full_posdummy() {
    log_info "Running Full POSDummy Integration Test..."
    
    # Prepare pytest command
    local cmd="python -m pytest backend/tests/test_pos_dummy.py --tb=short --no-cov"
    
    if $VERBOSE; then
        cmd="$cmd -v --capture=no -s"
    else
        cmd="$cmd -q"
    fi
    
    if $VERBOSE; then
        echo "Command: $cmd"
    fi
    
    if eval "$cmd"; then
        return 0
    else
        return 1
    fi
}

# Function to calculate and display duration
show_results() {
    local success=$1
    local end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    
    if [[ $success -eq 0 ]]; then
        log_celebration "POSDummy test PASSED in ${duration}s"
        echo "   HOMEPOT infrastructure is functional!"
    else
        log_error "POSDummy test FAILED after ${duration}s"
        echo "   HOMEPOT has structural issues that need attention!"
    fi
}

# Main execution function
main() {
    parse_args "$@"
    
    # Setup environment
    if ! setup_environment; then
        exit 1
    fi
    
    # Run tests based on mode
    local success=0
    
    if $QUICK; then
        if ! run_quick_posdummy; then
            success=1
        fi
    else
        if ! run_full_posdummy; then
            success=1
        fi
    fi
    
    # Show results
    show_results $success
    
    exit $success
}

# Handle interrupts gracefully
trap 'echo -e "\nPOSDummy test interrupted by user"; exit 1' INT TERM

# Run main function with all arguments
main "$@"
