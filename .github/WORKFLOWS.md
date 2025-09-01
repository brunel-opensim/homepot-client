# GitHub Workflows Documentation

This document describes the automated workflows configured**Repository Status:**
- **Visibility:** Public (enables GitHub security features)
- **Dependency Graph:** Enabled (confirmed in settings)
- **Dependency Review:** **Action still failing** (may need GitHub propagation time)
- **Alternative Scanning:** **Working** (pip-audit provides equivalent functionality)
- **GitHub Advanced Security:** Not required (public repository)the HOMEPOT Client repository, including how to monitor them and replicate them locally.

## Available Workflows

### 1. CI/CD Pipeline (`ci-cd.yml`)

**Trigger Events:**

- Push to `main` and `develop` branches
- Pull requests to `main` and `develop` branches
- Manual trigger via `workflow_dispatch`

**What it does:**2. Dependency Review Action Error:**

- **Issue:** `Dependency review is not supported on this repository. Please ensure that Dependency graph is enabled along with GitHub Advanced Security on private repositories`
- **Root Cause:** The dependency review action requires dependency graph to be enabled. For private repositories, this requires GitHub Advanced Security.
- **Current Status:** Repository is **public** with dependency graph enabled, but the action is still failing
- **Potential Causes:**
  - GitHub cache/propagation delay after repository visibility change
  - Action checking outdated repository metadata
  - Additional requirements not yet identified
- **Workaround:** **Alternative dependency security check** runs successfully via pip-audit
- **Impact:** Security scanning still functional, just using alternative method
- **Next Steps:** Monitor for GitHub propagation completion; dependency review may start working automaticallycurity scanning** (Bandit, Safety, Trivy vulnerability scanner)
- ### Key Notes
- **Dependency Review Issue:** The dependency review action is still failing with "not supported on this repository" despite the repository being public with dependency graph enabled. This appears to be a GitHub propagation delay or cache issue. We've implemented alternative scanning via `pip-audit` which provides equivalent functionality.
- **POSDummy Success:** The infrastructure testing gate consistently passes, providing reliable validation of system setup.
- **Monitoring:** Continue monitoring workflow runs for automatic resolution of the dependency review action while using the alternative scanning approach.
- **Cross-platform testing** across Ubuntu, Windows, and macOS
- **Multi-version Python support** (3.9, 3.11)
- **Code quality checks** (Black formatting, flake8 linting, isort, mypy)
- **Unit testing** with pytest and coverage reporting
- **Package building** and validation
- **Docker container testing**
- **Consortium partner notifications**

**Jobs Overview:**

```text
├── Security Scan
├── POSDummy Infrastructure Gate
├── Code Quality (Python 3.9, 3.11)
├── Test Suite (Ubuntu/Windows/macOS × Python 3.9/3.11)
├── Build Package
├── Docker Build & Test
└── Notify Consortium Partners
```

**POSDummy Infrastructure Gate:**
Early integration test inspired by FabSim3's FabDummy pattern. Verifies complete HOMEPOT infrastructure is functional before running expensive operations. Fast execution (2-3 minutes) with comprehensive coverage.

### 2. POSDummy Integration Test (`pos-dummy.yml`)

**Trigger Events:**

- Manual trigger with test mode selection (`full`, `quick`, `verbose`)
- Automatic trigger on core file changes
- Scheduled runs every 6 hours for continuous monitoring

**What it does:**

- **Infrastructure verification** across all critical HOMEPOT components
- **Fast feedback** for structural issues
- **Continuous monitoring** of repository health
- **Early detection** of breaking changes

**Test Phases:**
1. **Critical Imports** - Module loading and dependency verification
2. **API Endpoints** - FastAPI routing and accessibility
3. **Database Connectivity** - SQLAlchemy operations and integrity
4. **Complete Pipeline** - End-to-end site→device→job→agent→audit flow
5. **Configuration Integrity** - Package and config validation
6. **Package Structure** - Python module organization

### 3. Security Audit (`security-audit.yml`)

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
- **Dependency review for pull requests** (Available - repository is public with dependency graph enabled)

**Repository Status:**
- **Visibility:** Public (enables full GitHub security features)
- **Dependency Graph:** Enabled
- **Dependency Review:** Available for pull requests
- **GitHub Advanced Security:** Not required (public repository)

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
   - POSDummy Integration Test: [workflow link](https://github.com/brunel-opensim/homepot-client/actions/workflows/pos-dummy.yml)
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
gh workflow run "POSDummy Integration Test"
gh workflow run "Security Audit"
```

**Useful Workflow Monitoring:**

```bash
# Show status of latest runs
gh run list --workflow="CI/CD Pipeline" --limit 5
gh run list --workflow="POSDummy Integration Test" --limit 5
gh run list --workflow="Security Audit" --limit 5

# View logs of the latest run
gh run view --log $(gh run list --workflow="CI/CD Pipeline" --limit 1 --json databaseId --jq '.[0].databaseId')

# Download artifacts from latest run
gh run download $(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')

# Monitor POSDummy health
gh run list --workflow="POSDummy Integration Test" --limit 10
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

**Enhanced Validation Script:**

The `validate-workflows.sh` script now mirrors the complete GitHub Actions workflow:

```bash
# Run complete validation (matches CI/CD exactly)
./scripts/validate-workflows.sh

# Quick infrastructure check (POSDummy only)
./scripts/validate-workflows.sh --posdummy-only

# Specific validation modes
./scripts/validate-workflows.sh --code-only
./scripts/validate-workflows.sh --yaml-only
./scripts/validate-workflows.sh --no-tests --no-docs

# Verbose output for debugging
./scripts/validate-workflows.sh --verbose
./scripts/validate-workflows.sh --posdummy-only --verbose

# Fast development feedback
./scripts/validate-workflows.sh --fail-fast
```

**Validation Order (matches CI/CD):**
```text
YAML Syntax → Workflow Structure → POSDummy Gate → Code Quality → Python Setup → Documentation → Tests
```

**1. POSDummy Infrastructure Verification:**

```bash
# Quick infrastructure health check (2-3 minutes)
./scripts/run-pos-dummy.sh --quick

# Complete infrastructure verification
./scripts/run-pos-dummy.sh

# Detailed diagnostics
./scripts/run-pos-dummy.sh --verbose

# Integration via validation script
./scripts/validate-workflows.sh --posdummy-only
```

**2. Code Quality Checks:**

**2. Code Quality Checks:**

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

**3. Security Scanning:**

**3. Security Scanning:**

```bash
# Run security scans
bandit -r src/
safety check
pip-audit

# Run comprehensive security validation
./scripts/validate-workflows.sh --security-only
```

**4. Testing:**

```bash
# Run unit tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test categories
pytest tests/unit/ -v
pytest tests/integration/ -v

# POSDummy infrastructure testing
pytest tests/test_pos_dummy.py -v
```

**5. Package Building:**

```bash
# Build package
python -m build

# Validate package
twine check dist/*

# Install package locally
pip install -e .
```

**6. Docker Testing:**

```bash
# Test Docker setup
./scripts/test-docker.sh

# Manual Docker testing
docker build -t homepot-client .
docker run --rm homepot-client homepot-client --version
```

### Running POSDummy Tests Locally

POSDummy provides fast infrastructure verification inspired by FabSim3's FabDummy pattern:

**Basic Usage:**

```bash
# Quick health check (30 seconds)
./scripts/validate-workflows.sh --posdummy-only

# Standalone execution
./scripts/run-pos-dummy.sh --quick     # Fast mode
./scripts/run-pos-dummy.sh             # Full mode  
./scripts/run-pos-dummy.sh --verbose   # Detailed output
```

**Integration Testing:**

```bash
# Test critical imports and dependencies
pytest tests/test_pos_dummy.py::TestPOSDummy::test_critical_imports -v

# Test API endpoints
pytest tests/test_pos_dummy.py::TestPOSDummy::test_api_endpoints_available -v

# Test database connectivity
pytest tests/test_pos_dummy.py::TestPOSDummy::test_database_connectivity -v

# Complete pipeline test
pytest tests/test_pos_dummy.py::TestPOSDummy::test_complete_pos_dummy_pipeline -v
```

**Debugging Infrastructure Issues:**

```bash
# Verbose POSDummy analysis
./scripts/run-pos-dummy.sh --verbose

# Check specific phases
pytest tests/test_pos_dummy.py -v -k "critical_imports"
pytest tests/test_pos_dummy.py -v -k "database_connectivity"

# Integration via validation script
./scripts/validate-workflows.sh --posdummy-only --verbose
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

**1. POSDummy Infrastructure Test Failures:**

- **Issue:** POSDummy test fails with import errors
- **Solution:** Install package in development mode: `pip install -e .`

- **Issue:** POSDummy detects API endpoint failures
- **Solution:** Check if HOMEPOT services are properly configured; run `./scripts/run-pos-dummy.sh --verbose` for details

- **Issue:** Database connectivity issues in POSDummy
- **Solution:** Verify database setup and configuration; POSDummy uses temporary SQLite for testing

**2. Dependency Review Action Error:**

- **Issue:** `Dependency review is not supported on this repository. Please ensure that Dependency graph is enabled along with GitHub Advanced Security on private repositories`
- **Root Cause:** The dependency review action requires dependency graph to be enabled. For private repositories, this requires GitHub Advanced Security.
- **Solution:** Repository is now **public** with dependency graph enabled. The `actions/dependency-review-action@v4` should work properly.
- **Status:** **RESOLVED** - Repository converted to public, dependency graph is enabled
- **Technical Details:**
  - Dependency graph: Enabled (visible in repository settings)
  - Dependency review: Available for pull requests
  - Alternative scanning: Available for push/schedule events via pip-audit

**3. CodeQL Analysis Warnings:**

- **Issue:** "Advanced Security must be enabled"
- **Solution:** Expected for public repos without GitHub Enterprise; core scanning still works

**4. Test Failures:**

- **Issue:** Tests failing in CI but passing locally
- **Solution:** Check Python version compatibility and environment differences

**5. Security Scan Alerts:**

- **Issue:** New vulnerabilities detected
- **Solution:** Update dependencies with `pip install --upgrade` and rerun `safety check`

**6. Enhanced Validation Script Issues:**

- **Issue:** `./scripts/validate-workflows.sh` command not found
- **Solution:** Make script executable: `chmod +x scripts/validate-workflows.sh`

- **Issue:** Validation script fails with "Python not available"
- **Solution:** Ensure Python environment is activated and dependencies installed

### Getting Help

**Local Development Issues:**

```bash
# Run comprehensive validation with detailed output
./scripts/validate-workflows.sh --verbose

# Check POSDummy infrastructure health
./scripts/run-pos-dummy.sh --verbose

# Check installation
./scripts/install.sh --help
```

**Workflow-specific Issues:**

```bash
# View detailed logs
gh run view <run-id> --log

# Check workflow file syntax
./scripts/validate-workflows.sh --yaml-only

# Monitor POSDummy workflow health
gh run list --workflow="POSDummy Integration Test" --limit 5
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
- [POSDummy Documentation](../docs/POSDummy.md) - Infrastructure testing overview
- [POSDummy Integration Guide](../docs/POSDummy-Integration.md) - Detailed implementation guide
- [HOMEPOT Development Guide](../docs/development.md)
- [Security Best Practices](../docs/security.md)

**Last Updated:** September 2, 2025  
**Maintainers:** HOMEPOT Consortium Development Team
