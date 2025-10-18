# Frontend CI/CD Integration Guide

## Overview

This guide explains the frontend CI/CD checks added to the GitHub Actions workflow.

## Workflow: `frontend-checks.yml`

### Triggers

The workflow runs on:
- **Push** to `main`, `develop`, or any `feature/**` branch (only if frontend files change)
- **Pull requests** to `main` or `develop` (only if frontend files change)

### Jobs

#### 1. **Frontend Quality Checks**

Tests the frontend on multiple Node.js versions (20.x and 22.x) to ensure compatibility.

**Steps:**
- **Install dependencies** - Uses `npm ci` for consistent, clean installs
- **ESLint** - Checks code quality and style (linting)
- **Prettier** - Checks code formatting consistency
- **Build** - Verifies production build succeeds
- **Bundle size** - Reports build output size
- **Tests** - Runs Vitest tests with coverage reporting
- **Artifacts** - Uploads build output for review

**What it catches:**
- Syntax errors
- Import issues
- ESLint violations (code quality issues)
- Prettier violations (inconsistent formatting)
- Build failures
- Broken dependencies
- Test failures

#### 2. **Security Audit**

Checks for security vulnerabilities in dependencies.

**Steps:**
- **npm audit** - Scans for known vulnerabilities
- **Outdated packages** - Lists packages that need updates

**What it catches:**
- Security vulnerabilities (moderate and above)
- Outdated dependencies with known issues

#### 3. **Frontend Status Check**

Final summary job that reports overall status.

## Performance Optimizations

The workflow is optimized for speed:

1. **Path filtering** - Only runs when frontend files change
2. **Dependency caching** - npm packages are cached between runs
3. **Parallel jobs** - Quality checks and audit run simultaneously
4. **Matrix strategy** - Tests multiple Node versions in parallel

**Typical runtime:** 2-4 minutes

## What Gets Checked

### **Always Required (Blocks PR)**
- ESLint passes (code quality)
- Prettier check passes (code formatting)
- Production build succeeds
- All tests pass

### **Optional (Warns but doesn't block)**
- Security audit (informational)
- Outdated packages (informational)

## Local Development

Before pushing, you can run these checks locally:

```bash
cd frontend

# Run all checks
npm run lint           # ESLint (code quality)
npm run format:check   # Prettier (formatting)
npm run build          # Production build
npm run test           # Vitest tests with coverage
npm audit              # Security check

# Auto-fix issues
npm run lint:fix       # Auto-fix ESLint issues
npm run format         # Auto-format with Prettier
```

### Unified Validation Script

For convenience, you can run all frontend checks using the unified validation script:

```bash
# From project root - run all checks (backend + frontend)
./scripts/validate-workflows.sh

# Run only frontend checks
./scripts/validate-workflows.sh --frontend-only

# Run with verbose output
./scripts/validate-workflows.sh --frontend-only --verbose

# Skip frontend checks (only backend)
./scripts/validate-workflows.sh --no-frontend
```

This script matches exactly what the CI/CD pipeline runs, helping you catch issues before pushing.

## Configuration Files

- **ESLint**: `frontend/eslint.config.js` - Code quality rules
- **Prettier**: `frontend/.prettierrc` - Code formatting rules
- **Vite**: `frontend/vite.config.js` - Build configuration
- **Vitest**: `frontend/vitest.config.js` - Test configuration

## Code Quality Tools

The frontend uses industry-standard tools equivalent to Python's quality tools:

| Python Tool | JavaScript Equivalent | Purpose |
|-------------|----------------------|---------|
| **Black** | **Prettier** | Auto-formats code consistently |
| **Flake8** | **ESLint** | Lints code for quality issues |
| **MyPy** | **TypeScript** | Type checking (optional) |

**Prettier** ensures consistent code style (quotes, semicolons, indentation, line length).  
**ESLint** catches code quality issues (unused variables, missing imports, bad patterns).

## When Tests Are Added

The workflow is already configured to run tests. Once you implement tests:

1. Update the workflow to make tests **required** (remove `continue-on-error: true`)
2. Tests will run automatically on every PR
3. Coverage reports can be added later

## Monitoring Workflow Status

View workflow runs at:
```
https://github.com/brunel-opensim/homepot-client/actions
```

## Troubleshooting

### Build Fails in CI but works locally

**Cause:** Different Node.js version or environment variables

**Solution:**
1. Check the Node.js version in the workflow matches your local version
2. Ensure `.env.example` has all required variables
3. Verify no local `.env` files are being used unintentionally

### ESLint Failures

**Cause:** Code doesn't meet quality guidelines

**Solution:**
```bash
npm run lint          # See errors
npm run lint:fix      # Auto-fix when possible
```

### Prettier Formatting Failures

**Cause:** Code formatting doesn't match standards

**Solution:**
```bash
npm run format:check  # See which files need formatting
npm run format        # Auto-format all files
```

### Security Audit Warnings

**Cause:** Vulnerable dependencies detected

**Solution:**
```bash
npm audit fix         # Auto-fix minor issues
npm audit fix --force # Fix major issues (review changes!)
npm audit             # Review remaining issues
```

## Future Enhancements

Potential additions for the future:

- **Visual regression testing** - Screenshot comparisons
- **Code coverage** - Track test coverage percentage
- **Lighthouse CI** - Performance and accessibility scores
- **Bundle analysis** - Detailed size breakdown
- **License checking** - Verify dependency licenses
- **E2E tests** - Playwright/Cypress integration

## Questions?

See the main workflow documentation at `.github/WORKFLOWS.md`
