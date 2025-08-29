#!/bin/bash
# Comprehensive GitHub Actions Workflow Validator
# Validates workflows, dependencies, code quality, and common issues before pushing

set -e

echo "🔍 Comprehensive GitHub Workflow Validation"
echo "==========================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0

# Function to run a check
run_check() {
    local check_name="$1"
    local check_function="$2"
    
    echo -e "\n${BLUE}🔧 $check_name${NC}"
    echo "----------------------------------------"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    if $check_function; then
        echo -e "${GREEN}✅ $check_name: PASSED${NC}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "${RED}❌ $check_name: FAILED${NC}"
        return 1
    fi
}

# 1. Validate YAML syntax
validate_yaml_syntax() {
    local has_errors=false
    
    for file in .github/workflows/*.yml .github/workflows/*.yaml; do
        [ -f "$file" ] || continue
        
        echo -n "  Checking $(basename "$file"): "
        
        if python3 -c "import yaml; yaml.safe_load(open('$file', 'r'))" 2>/dev/null; then
            echo -e "${GREEN}Valid YAML${NC}"
        else
            echo -e "${RED}Invalid YAML${NC}"
            has_errors=true
        fi
    done
    
    [ "$has_errors" = false ]
}

# 2. Validate GitHub Actions structure
validate_actions_structure() {
    local has_errors=false
    
    for file in .github/workflows/*.yml .github/workflows/*.yaml; do
        [ -f "$file" ] || continue
        
        echo -n "  Checking $(basename "$file") structure: "
        
        python3 -c "
import yaml
import sys

try:
    with open('$file', 'r') as f:
        data = yaml.safe_load(f)
    
    # Check required fields - 'on' might be parsed as boolean True
    has_name = 'name' in data
    has_on = 'on' in data or True in data  # YAML parses 'on:' as True
    has_jobs = 'jobs' in data
    
    if not has_name:
        print('Missing name')
        sys.exit(1)
    if not has_on:
        print('Missing on/trigger configuration')
        sys.exit(1)
    if not has_jobs:
        print('Missing jobs')
        sys.exit(1)
    
    # Check jobs structure
    jobs = data['jobs']
    for job_name, job_config in jobs.items():
        if 'runs-on' not in job_config:
            print(f'Job {job_name} missing runs-on')
            sys.exit(1)
        
        if 'steps' not in job_config:
            print(f'Job {job_name} missing steps')
            sys.exit(1)
            
        # Check for deprecated actions
        steps = job_config.get('steps', [])
        for step in steps:
            if isinstance(step, dict) and 'uses' in step:
                action = step['uses']
                if '@v1' in action or '@v2' in action:
                    print(f'Warning: {action} may be deprecated')
    
    print('Valid')
    
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
" && echo -e "${GREEN}Valid${NC}" || { echo -e "${RED}Invalid${NC}"; has_errors=true; }
    done
    
    [ "$has_errors" = false ]
}

# 3. Check for deprecated GitHub Actions
check_deprecated_actions() {
    local has_warnings=false
    
    echo "  Scanning for deprecated actions..."
    
    # Common deprecated actions and their replacements
    declare -A deprecated_actions=(
        ["actions/setup-python@v2"]="actions/setup-python@v4 or v5"
        ["actions/setup-node@v2"]="actions/setup-node@v4"
        ["actions/checkout@v2"]="actions/checkout@v4"
        ["actions/checkout@v3"]="actions/checkout@v4"
        ["actions/upload-artifact@v2"]="actions/upload-artifact@v4"
        ["actions/upload-artifact@v3"]="actions/upload-artifact@v4"
        ["actions/download-artifact@v2"]="actions/download-artifact@v4"
        ["actions/download-artifact@v3"]="actions/download-artifact@v4"
    )
    
    for file in .github/workflows/*.yml .github/workflows/*.yaml; do
        [ -f "$file" ] || continue
        
        for deprecated in "${!deprecated_actions[@]}"; do
            if grep -q "$deprecated" "$file"; then
                echo -e "    ${YELLOW}⚠️  Found deprecated: $deprecated in $(basename "$file")${NC}"
                echo -e "    ${BLUE}💡 Consider upgrading to: ${deprecated_actions[$deprecated]}${NC}"
                has_warnings=true
            fi
        done
    done
    
    if [ "$has_warnings" = false ]; then
        echo "    No deprecated actions found"
    fi
    
    true  # Don't fail on warnings, just inform
}

# 4. Validate Python dependencies and setup
validate_python_setup() {
    echo "  Checking Python environment..."
    
    # Check if pyproject.toml exists and is valid
    if [ -f "pyproject.toml" ]; then
        echo -n "    pyproject.toml syntax: "
        if python3 -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))" 2>/dev/null; then
            echo -e "${GREEN}Valid${NC}"
        else
            echo -e "${RED}Invalid${NC}"
            return 1
        fi
    fi
    
    # Check if requirements files exist where referenced
    for file in .github/workflows/*.yml .github/workflows/*.yaml; do
        [ -f "$file" ] || continue
        
        # Check for specific requirements.txt references
        if grep -q "requirements\.txt" "$file"; then
            if [ ! -f "requirements.txt" ]; then
                echo -e "    ${RED}Missing referenced file: requirements.txt${NC}"
                return 1
            fi
        fi
        
        # Check for requirements-dev.txt or other variants
        if grep -q "requirements-.*\.txt" "$file"; then
            for req_file in requirements-*.txt; do
                if [ -f "$req_file" ]; then
                    echo "    Found requirements file: $req_file"
                fi
            done
        fi
    done
    
    echo "    Python setup looks good"
    return 0
}

# 5. Run code quality checks
validate_code_quality() {
    echo "  Running code quality checks..."
    
    # Check if code quality tools are properly configured
    local tools_configured=true
    
    # Check for Black configuration
    if command -v black >/dev/null 2>&1; then
        echo -n "    Black formatting: "
        if black --check src/ tests/ 2>/dev/null; then
            echo -e "${GREEN}Passed${NC}"
        else
            echo -e "${RED}Failed${NC}"
            tools_configured=false
        fi
    else
        echo -e "    ${YELLOW}Black not installed${NC}"
    fi
    
    # Check for isort configuration  
    if command -v isort >/dev/null 2>&1; then
        echo -n "    Import sorting: "
        if isort --check-only src/ tests/ 2>/dev/null; then
            echo -e "${GREEN}Passed${NC}"
        else
            echo -e "${RED}Failed${NC}"
            tools_configured=false
        fi
    else
        echo -e "    ${YELLOW}isort not installed${NC}"
    fi
    
    # Check for flake8
    if command -v flake8 >/dev/null 2>&1; then
        echo -n "    Linting (flake8): "
        if flake8 src/ tests/ 2>/dev/null; then
            echo -e "${GREEN}Passed${NC}"
        else
            echo -e "${RED}Failed${NC}"
            tools_configured=false
        fi
    else
        echo -e "    ${YELLOW}flake8 not installed${NC}"
    fi
    
    # Check for mypy
    if command -v mypy >/dev/null 2>&1; then
        echo -n "    Type checking (mypy): "
        if mypy src/ 2>/dev/null; then
            echo -e "${GREEN}Passed${NC}"
        else
            echo -e "${RED}Failed${NC}"
            tools_configured=false
        fi
    else
        echo -e "    ${YELLOW}mypy not installed${NC}"
    fi
    
    return $([ "$tools_configured" = true ] && echo 0 || echo 1)
}

# 6. Check Docker configuration
validate_docker_setup() {
    echo "  Checking Docker configuration..."
    
    local docker_valid=true
    
    # Check Dockerfile
    if [ -f "Dockerfile" ]; then
        echo -n "    Dockerfile syntax: "
        if docker build --dry-run . >/dev/null 2>&1 || grep -q "FROM" Dockerfile; then
            echo -e "${GREEN}Valid${NC}"
        else
            echo -e "${RED}Invalid${NC}"
            docker_valid=false
        fi
    else
        echo -e "    ${YELLOW}No Dockerfile found${NC}"
    fi
    
    # Check docker-compose files
    for compose_file in docker-compose.yml docker-compose.yaml; do
        if [ -f "$compose_file" ]; then
            echo -n "    $compose_file syntax: "
            # Try newer docker compose command first
            if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
                if docker compose -f "$compose_file" config >/dev/null 2>&1; then
                    echo -e "${GREEN}Valid${NC}"
                else
                    echo -e "${RED}Invalid${NC}"
                    docker_valid=false
                fi
            elif command -v docker-compose >/dev/null 2>&1; then
                if docker-compose -f "$compose_file" config >/dev/null 2>&1; then
                    echo -e "${GREEN}Valid${NC}"
                else
                    echo -e "${RED}Invalid${NC}"
                    docker_valid=false
                fi
            else
                # Basic YAML check if docker-compose not available
                if python3 -c "import yaml; yaml.safe_load(open('$compose_file', 'r'))" 2>/dev/null; then
                    echo -e "${YELLOW}Valid YAML (docker-compose not available)${NC}"
                    # Don't mark as invalid for missing docker-compose
                else
                    echo -e "${RED}Invalid YAML${NC}"
                    docker_valid=false
                fi
            fi
        fi
    done
    
    return $([ "$docker_valid" = true ] && echo 0 || echo 1)
}

# 7. Check for common workflow issues
check_workflow_issues() {
    echo "  Checking for common workflow issues..."
    
    local critical_issues_found=false
    
    for file in .github/workflows/*.yml .github/workflows/*.yaml; do
        [ -f "$file" ] || continue
        
        local filename=$(basename "$file")
        
        # Check for missing permissions
        if grep -q "pages\|deploy\|release" "$file" && ! grep -q "permissions:" "$file"; then
            echo -e "    ${YELLOW}⚠️  $filename: Consider adding explicit permissions${NC}"
        fi
        
        # Check for hardcoded secrets (avoid false positives)
        if grep -E "password\s*:\s*['\"][^'\"]*['\"]|token\s*:\s*['\"][^'\"]*['\"]|key\s*:\s*['\"][^'\"]*['\"]" "$file" >/dev/null; then
            echo -e "    ${RED}🔒 $filename: Potential hardcoded secrets detected${NC}"
            critical_issues_found=true
        fi
        
        # Check for missing error handling (advisory)
        if grep -q "run:" "$file" && ! grep -q "set -e\|continue-on-error" "$file"; then
            echo -e "    ${YELLOW}💡 $filename: Consider adding error handling${NC}"
        fi
        
        # Check for missing timeout (advisory)
        if grep -q "timeout-minutes:" "$file"; then
            echo -e "    ${GREEN}✓ $filename: Has timeout configured${NC}"
        else
            echo -e "    ${YELLOW}💡 $filename: Consider adding timeout-minutes${NC}"
        fi
    done
    
    return $([ "$critical_issues_found" = false ] && echo 0 || echo 1)
}

# 8. Check branch protection requirements
check_branch_requirements() {
    echo "  Checking branch and repository requirements..."
    
    # Check if we're on the right branch
    current_branch=$(git branch --show-current)
    echo "    Current branch: $current_branch"
    
    # Check for uncommitted changes
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo -e "    ${YELLOW}⚠️  Uncommitted changes detected${NC}"
        echo -e "    ${BLUE}💡 Consider committing changes before validation${NC}"
    else
        echo -e "    ${GREEN}✓ Working directory clean${NC}"
    fi
    
    # Check remote configuration
    if git remote get-url origin >/dev/null 2>&1; then
        remote_url=$(git remote get-url origin)
        echo "    Remote origin: $remote_url"
    else
        echo -e "    ${YELLOW}⚠️  No remote origin configured${NC}"
    fi
    
    return 0
}

# Main execution
main() {
    echo "Starting comprehensive validation..."
    
    # Run all checks
    run_check "YAML Syntax Validation" validate_yaml_syntax
    run_check "GitHub Actions Structure" validate_actions_structure  
    run_check "Deprecated Actions Check" check_deprecated_actions
    run_check "Python Setup Validation" validate_python_setup
    run_check "Code Quality Checks" validate_code_quality
    run_check "Docker Configuration" validate_docker_setup
    run_check "Workflow Issues Check" check_workflow_issues
    run_check "Branch Requirements" check_branch_requirements
    
    # Final summary
    echo -e "\n${BLUE}📊 Validation Summary${NC}"
    echo "==========================================="
    echo "Total checks: $TOTAL_CHECKS"
    echo "Passed: $PASSED_CHECKS"
    echo "Failed: $((TOTAL_CHECKS - PASSED_CHECKS))"
    
    if [ $PASSED_CHECKS -eq $TOTAL_CHECKS ]; then
        echo -e "\n${GREEN}🎉 All checks passed! Ready to push! 🚀${NC}"
        exit 0
    else
        echo -e "\n${RED}❌ Some checks failed. Please fix issues before pushing.${NC}"
        echo -e "${BLUE}💡 Run individual tools to get detailed error information.${NC}"
        exit 1
    fi
}

# Check if running in GitHub Actions
if [ "$GITHUB_ACTIONS" = "true" ]; then
    echo "🤖 Running in GitHub Actions environment"
fi

# Run main function
main
