#!/bin/bash
# Simple GitHub Actions Workflow Validator
# Validates basic workflow syntax and runs essential code quality checks

set -e

echo "🔍 Simple Workflow & Code Quality Validation"
echo "============================================"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0

# Function to run a check
run_check() {
    local check_name="$1"
    local check_command="$2"
    
    echo -e "\n🔧 $check_name"
    echo "----------------------------------------"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    if eval "$check_command"; then
        echo -e "${GREEN}✅ $check_name: PASSED${NC}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "${RED}❌ $check_name: FAILED${NC}"
        return 1
    fi
}

# 1. Validate YAML syntax
validate_yaml() {
    for file in .github/workflows/*.yml .github/workflows/*.yaml; do
        [ -f "$file" ] || continue
        echo -n "  Checking $(basename "$file"): "
        if python3 -c "import yaml; yaml.safe_load(open('$file', 'r'))" 2>/dev/null; then
            echo -e "${GREEN}Valid${NC}"
        else
            echo -e "${RED}Invalid YAML${NC}"
            return 1
        fi
    done
    return 0
}

# 2. Basic workflow structure check
validate_structure() {
    for file in .github/workflows/*.yml .github/workflows/*.yaml; do
        [ -f "$file" ] || continue
        echo -n "  Checking $(basename "$file"): "
        if grep -q "^name:" "$file" && grep -q "^on:\|^true:" "$file" && grep -q "^jobs:" "$file"; then
            echo -e "${GREEN}Valid structure${NC}"
        else
            echo -e "${RED}Missing required fields${NC}"
            return 1
        fi
    done
    return 0
}

# 3. Essential code quality
validate_code_quality() {
    echo "  Running essential code quality checks..."
    
    # Black formatting
    if command -v black >/dev/null 2>&1; then
        echo -n "    Black formatting: "
        if black --check src/ tests/ 2>/dev/null; then
            echo -e "${GREEN}Passed${NC}"
        else
            echo -e "${RED}Failed - run: black src/ tests/${NC}"
            return 1
        fi
    fi
    
    # flake8 linting
    if command -v flake8 >/dev/null 2>&1; then
        echo -n "    Linting (flake8): "
        if flake8 src/ tests/ 2>/dev/null; then
            echo -e "${GREEN}Passed${NC}"
        else
            echo -e "${RED}Failed - run: flake8 src/ tests/${NC}"
            return 1
        fi
    fi
    
    return 0
}

# 4. Basic Python setup
validate_python() {
    echo "  Checking Python setup..."
    
    if [ -f "pyproject.toml" ]; then
        echo -n "    pyproject.toml: "
        if python3 -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))" 2>/dev/null; then
            echo -e "${GREEN}Valid${NC}"
        else
            echo -e "${RED}Invalid${NC}"
            return 1
        fi
    fi
    
    if [ -f "requirements.txt" ]; then
        echo "    requirements.txt: Found"
    fi
    
    return 0
}

# Main execution
main() {
    echo "Running essential validation checks..."
    
    # Run core checks only
    run_check "YAML Syntax" "validate_yaml"
    run_check "Workflow Structure" "validate_structure"
    run_check "Code Quality" "validate_code_quality"
    run_check "Python Setup" "validate_python"
    
    # Final summary
    echo -e "\n📊 Validation Summary"
    echo "====================================="
    echo "Total checks: $TOTAL_CHECKS"
    echo "Passed: $PASSED_CHECKS"
    echo "Failed: $((TOTAL_CHECKS - PASSED_CHECKS))"
    
    if [ $PASSED_CHECKS -eq $TOTAL_CHECKS ]; then
        echo -e "\n${GREEN}🎉 All essential checks passed!${NC}"
        echo -e "${GREEN}Repository is ready for development.${NC}"
        exit 0
    else
        echo -e "\n${RED}❌ Some checks failed.${NC}"
        echo -e "${YELLOW}💡 Fix the issues above before pushing.${NC}"
        exit 1
    fi
}

# Run main function
main
