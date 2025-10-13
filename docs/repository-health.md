# Repository Health Checks

HOMEPOT includes automated repository health checks to prevent common structural issues and maintain code quality.

## Overview

The repository health system consists of:

1. **Automated GitHub Workflow** - Runs on every PR and push
2. **Local Health Check Script** - Optional pre-commit validation
3. **Comprehensive .gitignore** - Prevents accidental commits

## Automated GitHub Workflow

The **Repository Health Check** workflow (`.github/workflows/repository-health.yml`) automatically validates:

### What It Checks

#### 1. Dependency Directories BLOCKING
- **node_modules/** - Node.js dependencies (should never be committed)
- **venv/, .venv/, env/** - Python virtual environments
- **__pycache__/** - Python bytecode cache

**Why this matters**: Committing dependencies bloats the repository, causes merge conflicts, and creates security risks.

#### 2. Large Files WARNING
- Files larger than 5MB
- Suggests using Git LFS for large binaries

**Why this matters**: Large files slow down git operations and waste storage.

#### 3. Sensitive Files WARNING
- `.env` files with credentials
- Private keys (`.pem`, `.key`, `.p12`)
- SSH keys (`id_rsa`)
- Credentials files

**Why this matters**: Prevents accidental exposure of secrets and credentials.

#### 4. .gitignore Completeness WARNING
- Validates common patterns are present
- Suggests missing entries

#### 5. PR Size Analysis WARNING
- Warns about very large PRs (>50,000 lines)
- Suggests breaking into smaller PRs

**Why this matters**: Large PRs often indicate committed dependencies or should be split for better review.

## Using the Local Health Check Script

### Quick Usage

```bash
# Run before committing
./scripts/check-repo-health.sh
```

### What It Checks

The local script validates:

- No node_modules/ in git
- No Python virtual environments
- No __pycache__ directories
- No .pyc files
- Large files (>5MB)
- Potentially sensitive files
- .gitignore completeness
- Unstaged changes
- Commit message length

### Exit Codes

- `0` - All checks passed
- `1` - Critical issues found (blocking)
- Warnings don't block but should be reviewed

### Example Output

```bash
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOMEPOT Repository Health Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Checking for node_modules...
No node_modules in repository

Checking for Python virtual environments...
No virtual environments in repository

Checking for __pycache__...
No __pycache__ in repository

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Health Check Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Repository is healthy!
```

## Setting Up Pre-commit Hook (Optional)

To automatically run health checks before every commit:

```bash
# Create pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
./scripts/check-repo-health.sh
EOF

# Make it executable
chmod +x .git/hooks/pre-commit
```

Now the health check runs automatically before each commit. If critical issues are found, the commit is blocked.

## Common Issues and Fixes

### Issue: node_modules/ Committed

**Symptoms:**
```
ERROR: node_modules/ directory found in repository!
```

**Fix:**
```bash
# Remove from git (keeps local copy)
git rm -r --cached homepot-frontend/node_modules/

# Add to .gitignore
echo "node_modules/" >> .gitignore

# Commit the fix
git commit -m "fix: remove node_modules from git tracking"
```

### Issue: Python Virtual Environment Committed

**Symptoms:**
```
ERROR: Virtual environment found in git!
```

**Fix:**
```bash
# Remove from git
git rm -r --cached venv/ .venv/ env/

# Already in .gitignore, just commit
git commit -m "fix: remove virtual environment from git"
```

### Issue: __pycache__ Committed

**Symptoms:**
```
ERROR: __pycache__ directories found in git!
```

**Fix:**
```bash
# Remove all __pycache__ directories
find . -type d -name __pycache__ -exec git rm -r --cached {} + 2>/dev/null

# Already in .gitignore, just commit
git commit -m "fix: remove __pycache__ from git"
```

### Issue: Large File Warning

**Symptoms:**
```
WARNING: Found 1 large files (>5MB)
```

**Fix:**
```bash
# Option 1: Use Git LFS
git lfs track "*.bin"
git add .gitattributes

# Option 2: Move to external storage
# Store large files in S3, artifactory, etc.
# Keep only small reference files in git
```

## Best Practices

### What SHOULD Be Committed

Source code files (`.py`, `.js`, `.ts`, etc.)  
Configuration templates (`.example`, `.sample`)  
Documentation (`.md`, `.rst`)  
Tests  
`requirements.txt`, `package.json`, `package-lock.json`  
`.gitignore`, `.dockerignore`  
CI/CD workflows (`.github/workflows/`)  

### What SHOULD NOT Be Committed

Dependencies (`node_modules/`, `venv/`)  
Build artifacts (`dist/`, `build/`, `*.pyc`)  
IDE settings (`.vscode/`, `.idea/` - personal preferences only)  
Environment files with secrets (`.env`, `.env.local`)  
Log files (`*.log`)  
Database files (except demo data)  
Large binary files (without Git LFS)  
Temporary files (`tmp/`, `temp/`, `*.tmp`)  

## Workflow Integration

### In Pull Requests

When you create a PR, the Repository Health Check workflow runs automatically:

1. **Checks are visible** in the PR checks section
2. **Blocking issues** will fail the CI pipeline
3. **Warnings** don't block but should be addressed
4. **Summary** appears in workflow logs

### Viewing Results

```bash
# Check latest workflow run
gh run list --workflow=repository-health.yml --limit 1

# View detailed results
gh run view <run-id> --log
```

## Troubleshooting

### Workflow Not Running

Check that:
1. Workflow file exists: `.github/workflows/repository-health.yml`
2. Branch is `main` or `develop` (or you're in a PR targeting these)
3. GitHub Actions are enabled for the repository

### False Positives

If the health check flags legitimate files:

1. **For test files**: Include keywords like `test`, `mock`, `example` in filename
2. **For build artifacts**: Add to `.gitignore` if they should be excluded
3. **For large files**: Consider using Git LFS

### Getting Help

1. Run local health check: `./scripts/check-repo-health.sh`
2. Check workflow logs: `gh run view --log`
3. Review this documentation
4. Ask in team chat or create an issue

## Maintenance

### Updating Health Checks

To add new checks:

1. Edit `.github/workflows/repository-health.yml` for CI
2. Edit `scripts/check-repo-health.sh` for local checks
3. Update this documentation
4. Test locally before committing

### Updating .gitignore

```bash
# Test what would be ignored
git check-ignore -v <file>

# Test pattern matching
git ls-files --ignored --exclude-standard
```

## Benefits

**Prevents mistakes** - Catches issues before they reach main  
**Saves time** - Automated checks are faster than manual review  
**Teaches best practices** - Developers learn from error messages  
**Maintains quality** - Consistent standards across the team  
**Protects secrets** - Prevents accidental credential exposure  
**Keeps repo clean** - No bloat from unnecessary files  

## Related Documentation

- [Collaboration Guide](collaboration-guide.md) - Team workflow and standards
- [Development Guide](development-guide.md) - Local development setup
- [GitHub Permissions Guide](github-permissions-guide.md) - Access control

---

*The repository health check system helps maintain HOMEPOT's code quality standards automatically. For questions or issues, see the troubleshooting section above or contact the team.*
