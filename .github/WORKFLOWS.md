# GitHub Workflows Documentation

This document describes the automated workflows configured for the HOMEPOT Client repository, including how to monitor them and replicate them locally.

## Available Workflows

### 1. CI/CD Pipeline (`ci-cd.yml`)

**Trigger Events:**

- Push to `main` branch
- Pull requests to `main` branch
- Manual trigger via `workflow_dispatch`

**What it does:**

- **Cross-platform testing** across Ubuntu, Windows, and macOS
- **Multi-version Python support** (3.9, 3.11, 3.12)
- **Code quality checks** (Black formatting, flake8 linting, import sorting)
- **Security scanning** (Bandit, Safety)
- **Unit testing** with pytest and coverage reporting
- **Package building** and validation
- **Docker container testing**
- **Consortium partner notifications**

**Jobs Overview:**

```text
├── Code Quality (Python 3.9, 3.11)
├── Security Scan
├── Test Suite (Ubuntu/Windows/macOS × Python 3.9/3.11)
├── Build Package
├── Docker Build & Test
└── Notify Consortium Partners
```

### 2. Security Audit (`security-audit.yml`)

**Trigger Events:**

- Scheduled weekly (Mondays at 9 AM UTC)
- Push to `main` when security-related files change
- Pull requests affecting dependency files
- Manual trigger via `workflow_dispatch`

**What it does:**

- **Dependency vulnerability scanning** (pip-audit, Safety)
- **Static code analysis** (Bandit, CodeQL when available)
- **Secret scanning** (TruffleHog)
- **License compliance verification**
- **Consortium security standards validation**
- **Security report generation**

**Jobs Overview:**

```text
├── Security Vulnerability Audit
│   ├── Dependency Review (PR only)
│   ├── Safety & Bandit scans
│   └── CodeQL analysis
├── Secret Scanning
│   ├── Recent commits (push events)
│   └── Full repository scan (scheduled)
└── Consortium Compliance Check
    ├── License validation
    ├── Package metadata check
    └── Security report generation
```

## Monitoring Workflows

### Using GitHub Web Interface

1. **View all workflows:**

   ```url
   https://github.com/brunel-opensim/homepot-client/actions
   ```

2. **View specific workflow:**

   - CI/CD Pipeline: [workflow link](https://github.com/brunel-opensim/homepot-client/actions/workflows/ci-cd.yml)
   - Security Audit: [workflow link](https://github.com/brunel-opensim/homepot-client/actions/workflows/security-audit.yml)

### Using GitHub CLI

**Prerequisites:**

```bash
# Install GitHub CLI (if not already installed)
# Ubuntu/Debian: sudo apt install gh
# macOS: brew install gh
# Windows: winget install GitHub.cli

# Authenticate
gh auth login
```

**Basic Commands:**

```bash
# List all workflows
gh workflow list

# View recent workflow runs
gh run list --limit 10

# View specific workflow run details
gh run view <run-id>

# View workflow run logs
gh run view <run-id> --log

# Watch a running workflow
gh run watch <run-id>

# Trigger a workflow manually
gh workflow run "CI/CD Pipeline"
gh workflow run "Security Audit"
```

**Useful Workflow Monitoring:**

```bash
# Show status of latest runs
gh run list --workflow="CI/CD Pipeline" --limit 5
gh run list --workflow="Security Audit" --limit 5

# View logs of the latest run
gh run view --log $(gh run list --workflow="CI/CD Pipeline" --limit 1 --json databaseId --jq '.[0].databaseId')

# Download artifacts from latest run
gh run download $(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')
```

## Running Workflows Locally

### Prerequisites

```bash
# Clone the repository
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client

# Set up development environment
./scripts/install.sh --dev
source scripts/activate-homepot.sh
```

### Replicating CI/CD Pipeline Locally

**1. Code Quality Checks:**

```bash
# Run all validation (equivalent to CI/CD checks)
./scripts/validate-workflows.sh

# Individual quality checks
./scripts/validate-workflows.sh --code-only
./scripts/validate-workflows.sh --yaml-only

# Format code (Black)
black src/ tests/
isort src/ tests/

# Lint code (flake8)
flake8 src/ tests/

# Type checking (mypy)
mypy src/
```

**2. Security Scanning:**

```bash
# Run security scans
bandit -r src/
safety check
pip-audit

# Run comprehensive security validation
./scripts/validate-workflows.sh --security-only
```

**3. Testing:**

```bash
# Run unit tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test categories
pytest tests/unit/ -v
pytest tests/integration/ -v
```

**4. Package Building:**

```bash
# Build package
python -m build

# Validate package
twine check dist/*

# Install package locally
pip install -e .
```

**5. Docker Testing:**

```bash
# Test Docker setup
./scripts/test-docker.sh

# Manual Docker testing
docker build -t homepot-client .
docker run --rm homepot-client homepot-client --version
```

### Replicating Security Audit Locally

**1. Dependency Security:**

```bash
# Check for known vulnerabilities
safety check --json
pip-audit --format=json

# Full dependency tree analysis
pip-tree
```

**2. Secret Scanning:**

```bash
# Install TruffleHog (if available)
# Scan for secrets in recent commits
git log --oneline -10 | head -5

# Manual secret pattern search
grep -r -i "password\|secret\|key\|token" --include="*.py" src/
```

**3. Compliance Checks:**

```bash
# Verify license
cat LICENSE

# Check package metadata
python -m build
twine check dist/*

# Validate project structure
ls -la pyproject.toml requirements.txt src/
```

## Workflow Status & Troubleshooting

### Common Issues and Solutions

**1. Dependency Review Action Error:**

- **Issue:** `actions/dependency-review-action` requires base/head refs
- **Solution:** Now runs only on pull requests; push events use alternative scanning

**2. CodeQL Analysis Warnings:**

- **Issue:** "Advanced Security must be enabled"
- **Solution:** Expected for public repos without GitHub Enterprise; core scanning still works

**3. Test Failures:**

- **Issue:** Tests failing in CI but passing locally
- **Solution:** Check Python version compatibility and environment differences

**4. Security Scan Alerts:**

- **Issue:** New vulnerabilities detected
- **Solution:** Update dependencies with `pip install --upgrade` and rerun `safety check`

### Getting Help

**Local Development Issues:**

```bash
# Run comprehensive validation
./scripts/validate-workflows.sh --verbose

# Check installation
./scripts/install.sh --help
```

**Workflow-specific Issues:**

```bash
# View detailed logs
gh run view <run-id> --log

# Check workflow file syntax
./scripts/validate-workflows.sh --yaml-only
```

**Consortium Support:**

- Review security compliance requirements
- Check artifact uploads in workflow runs
- Verify notification settings for partners

## Best Practices

### Before Pushing Code

1. **Run local validation:**

   ```bash
   ./scripts/validate-workflows.sh
   ```

2. **Test installation:**

   ```bash
   ./scripts/install.sh --venv test-env --dev
   ```

3. **Check security:**

   ```bash
   safety check
   bandit -r src/
   ```

### For Pull Requests

1. **Ensure dependency changes are reviewed:**

   - The `dependency-review-action` will automatically analyze changes
   - Update `requirements.txt` if needed

2. **Include security considerations:**

   - New dependencies should be from trusted sources
   - Update security documentation if needed

3. **Test across platforms:**

   - Workflows test Ubuntu, Windows, and macOS
   - Consider platform-specific issues

### Monitoring Best Practices

1. **Regular checks:**

   ```bash
   # Weekly workflow status check
   gh run list --limit 20 | grep -E "(✓|X)"
   ```

2. **Artifact management:**

   ```bash
   # Download security reports
   gh run download --name security-audit-report
   ```

3. **Performance monitoring:**

   - Watch for increasing workflow duration
   - Monitor artifact sizes

---

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub CLI Manual](https://cli.github.com/manual/)
- [HOMEPOT Development Guide](../docs/development.md)
- [Security Best Practices](../docs/security.md)

**Last Updated:** August 30, 2025  
**Maintainers:** HOMEPOT Consortium Development Team
