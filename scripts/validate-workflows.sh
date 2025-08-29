#!/bin/bash
# GitHub Actions Workflow Validator
# Validates YAML syntax and GitHub Actions structure

set -e

echo "Validating GitHub Actions workflows..."

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to validate YAML syntax
validate_yaml() {
    local file="$1"
    echo -n "  $(basename "$file"): "
    
    if python3 -c "import yaml; yaml.safe_load(open('$file', 'r'))" 2>/dev/null; then
        echo -e "${GREEN} Valid YAML${NC}"
        return 0
    else
        echo -e "${RED} Invalid YAML${NC}"
        return 1
    fi
}

# Function to check GitHub Actions structure
validate_github_actions() {
    local file="$1"
    echo -n "  $(basename "$file") structure: "
    
    python3 -c "
import yaml
import sys

try:
    with open('$file', 'r') as f:
        data = yaml.safe_load(f)
    
    # Check required fields
    if 'name' not in data:
        print('Missing workflow name')
        sys.exit(1)
    
    if 'on' not in data:
        print('Missing trigger configuration')
        sys.exit(1)
    
    if 'jobs' not in data:
        print('Missing jobs configuration')
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
    
    print('Valid structure')
    
except Exception as e:
    print(f'Structure error: {e}')
    sys.exit(1)
" 2>/dev/null && echo -e "${GREEN}Valid structure${NC}" || echo -e "${RED}Invalid structure${NC}"
}

# Find all workflow files
workflow_files=$(find .github/workflows -name "*.yml" -o -name "*.yaml" 2>/dev/null || true)

if [ -z "$workflow_files" ]; then
    echo -e "${YELLOW} No workflow files found${NC}"
    exit 0
fi

# Validate each workflow file
total_files=0
valid_files=0

for file in $workflow_files; do
    echo "Validating: $file"
    total_files=$((total_files + 1))
    
    if validate_yaml "$file" && validate_github_actions "$file"; then
        valid_files=$((valid_files + 1))
        echo -e "  ${GREEN} $file is valid${NC}"
    else
        echo -e "  ${RED} $file has issues${NC}"
    fi
    echo
done

# Summary
echo "Validation Summary:"
echo "  Total files: $total_files"
echo "  Valid files: $valid_files"

if [ $valid_files -eq $total_files ]; then
    echo -e "${GREEN} All workflow files are valid!${NC}"
    exit 0
else
    echo -e "${RED} Some workflow files have issues${NC}"
    exit 1
fi
