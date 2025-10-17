#!/bin/bash
# Repository Health Check Script
# This script checks for common repository issues before committing
# Usage: ./scripts/check-repo-health.sh

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "HOMEPOT Repository Health Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

ISSUES_FOUND=0
WARNINGS=0

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to print colored output
print_error() {
    echo -e "${RED}ERROR: $1${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
}

print_warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
    WARNINGS=$((WARNINGS + 1))
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

# Check 1: node_modules
echo "Checking for node_modules..."
if git ls-files | grep -q 'node_modules/'; then
    print_error "node_modules/ directory found in git!"
    echo "   Run: git rm -r --cached **/node_modules/"
    echo "   Add 'node_modules/' to .gitignore"
else
    print_success "No node_modules in repository"
fi
echo ""

# Check 2: Python virtual environments
echo "Checking for Python virtual environments..."
if git ls-files | grep -qE '^(venv|\.venv|env|\.env)/'; then
    print_error "Virtual environment found in git!"
    echo "   Run: git rm -r --cached venv/ .venv/ env/ .env/"
    echo "   Add 'venv/', '.venv/' to .gitignore"
else
    print_success "No virtual environments in repository"
fi
echo ""

# Check 3: __pycache__
echo "Checking for __pycache__..."
if git ls-files | grep -q '__pycache__/'; then
    print_error "__pycache__ directories found in git!"
    echo "   Run: git rm -r --cached **/__pycache__/"
    echo "   Add '__pycache__/' to .gitignore"
else
    print_success "No __pycache__ in repository"
fi
echo ""

# Check 4: .pyc files
echo "Checking for .pyc files..."
if git ls-files | grep -q '\.pyc$'; then
    print_error ".pyc files found in git!"
    echo "   Run: git rm --cached **/*.pyc"
    echo "   Add '*.pyc' to .gitignore"
else
    print_success "No .pyc files in repository"
fi
echo ""

# Check 5: Large files
echo "Checking for large files (>5MB)..."
LARGE_FILES=$(git ls-files | xargs ls -l 2>/dev/null | awk '$5 > 5242880 {print $9}' | wc -l)
if [ "$LARGE_FILES" -gt 0 ]; then
    print_warning "Found $LARGE_FILES large files (>5MB)"
    echo "   Consider using Git LFS: https://git-lfs.github.com/"
    git ls-files | xargs ls -lh 2>/dev/null | awk '$5 ~ /M$/ && $5+0 > 5 {print "   " $9 " (" $5 ")"}'
else
    print_success "No excessively large files"
fi
echo ""

# Check 6: Sensitive file patterns
echo "Checking for potentially sensitive files..."
SENSITIVE_FOUND=0
SENSITIVE_PATTERNS=(
    "\.env$"
    "\.pem$"
    "\.key$"
    "id_rsa"
    "secret"
    "password"
    "credentials\.json$"
)

for pattern in "${SENSITIVE_PATTERNS[@]}"; do
    MATCHES=$(git ls-files | grep -iE "$pattern" | grep -vE '(example|sample|template|test|mock|dummy|\.md)' || true)
    if [ -n "$MATCHES" ]; then
        print_warning "Files matching sensitive pattern '$pattern':"
        echo "$MATCHES" | sed 's/^/   /'
        SENSITIVE_FOUND=1
    fi
done

if [ $SENSITIVE_FOUND -eq 0 ]; then
    print_success "No obviously sensitive files found"
fi
echo ""

# Check 7: .gitignore exists and has coverage
echo "Checking .gitignore..."
if [ ! -f .gitignore ]; then
    print_error ".gitignore file not found!"
else
    MISSING_PATTERNS=()
    REQUIRED_PATTERNS=(
        "__pycache__"
        "*.pyc"
        "venv"
        "node_modules"
        "*.log"
        ".env"
    )
    
    for pattern in "${REQUIRED_PATTERNS[@]}"; do
        if ! grep -q "$pattern" .gitignore; then
            MISSING_PATTERNS+=("$pattern")
        fi
    done
    
    if [ ${#MISSING_PATTERNS[@]} -gt 0 ]; then
        print_warning ".gitignore missing recommended patterns:"
        printf '   %s\n' "${MISSING_PATTERNS[@]}"
    else
        print_success ".gitignore has good coverage"
    fi
fi
echo ""

# Check 8: Unstaged changes
echo "Checking for unstaged changes..."
if [ -n "$(git status --porcelain | grep '^.[MD]')" ]; then
    print_warning "You have unstaged changes"
    echo "   Run: git add -A"
else
    print_success "All changes are staged"
fi

# Check 9: Commit message length (for last commit if exists)
if git log -1 --pretty=%B 2>/dev/null | head -1 | awk '{if (length($0) > 72) exit 1}'; then
    true # Commit message is good or no commits yet
else
    print_warning "Last commit message subject line is too long (>72 chars)"
    echo "   Keep subject lines under 72 characters"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Health Check Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $ISSUES_FOUND -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    print_success "Repository is healthy!"
    echo ""
    exit 0
elif [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${YELLOW}Found $WARNINGS warnings (non-blocking)${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}Found $ISSUES_FOUND critical issues!${NC}"
    echo -e "${YELLOW}Found $WARNINGS warnings${NC}"
    echo ""
    echo "Please fix critical issues before committing."
    exit 1
fi
