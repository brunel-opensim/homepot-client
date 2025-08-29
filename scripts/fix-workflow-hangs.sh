#!/bin/bash
# Fix common GitHub Actions workflow hanging issues

set -e

echo "🔧 Fixing GitHub Actions workflow hanging issues..."

# Add timeout-minutes to workflows
echo "📝 Adding timeout configuration to workflows..."

# Function to add timeout to a job if not present
add_timeout_to_job() {
    local file="$1"
    local job_name="$2"
    local timeout="${3:-30}"
    
    if ! grep -A 5 "^  ${job_name}:" "$file" | grep -q "timeout-minutes:"; then
        echo "  Adding timeout to $job_name in $(basename $file)"
        # This is a simplified approach - in practice you'd use a YAML parser
        sed -i "/^  ${job_name}:/a\\    timeout-minutes: ${timeout}" "$file"
    fi
}

# Check for dependency installation issues
echo "🔍 Checking for potential dependency installation hangs..."

for file in .github/workflows/*.yml; do
    [ -f "$file" ] || continue
    
    echo "Checking $(basename "$file")..."
    
    # Check for pip install without --no-cache-dir (can hang on low memory)
    if grep -q "pip install" "$file" && ! grep -q "\--no-cache-dir" "$file"; then
        echo "  ⚠️  Warning: pip install without --no-cache-dir may hang on low memory"
    fi
    
    # Check for missing set -e in run commands
    if grep -A 10 "run:" "$file" | grep -v "set -e" | grep -q "pip install\|apt-get\|wget\|curl"; then
        echo "  💡 Consider adding 'set -e' to fail fast on errors"
    fi
    
    # Check for resource-intensive operations without timeout
    if grep -q "docker\|build\|compile\|install\|download" "$file"; then
        if ! grep -q "timeout-minutes:" "$file"; then
            echo "  ⚠️  Resource-intensive operations without timeout detected"
        fi
    fi
done

echo ""
echo "🚀 Recommendations to fix workflow hangs:"
echo "=========================================="
echo ""
echo "1. Add timeout-minutes to all jobs (especially security scans)"
echo "2. Use --no-cache-dir with pip install to reduce memory usage"
echo "3. Add 'set -e' to shell commands for fail-fast behavior"
echo "4. Consider reducing Python matrix size if workflows are slow"
echo "5. Add continue-on-error: true for non-critical steps"
echo ""

# Generate a patch file with fixes
cat > workflow-hang-fixes.patch << 'EOF'
# Suggested fixes for workflow hanging issues

# 1. Add to all jobs in .github/workflows/*.yml:
    timeout-minutes: 30

# 2. Replace pip install commands with:
        pip install --no-cache-dir -r requirements.txt

# 3. Add to beginning of run commands:
        set -e

# 4. For non-critical steps, add:
        continue-on-error: true

# 5. Consider reducing matrix from:
        python-version: ['3.9', '3.10', '3.11', '3.12']
# to:
        python-version: ['3.9', '3.11']
EOF

echo "📄 Generated workflow-hang-fixes.patch with detailed recommendations"
echo ""
echo "🔧 To apply automatic fixes, run:"
echo "   ./scripts/apply-workflow-fixes.sh"
