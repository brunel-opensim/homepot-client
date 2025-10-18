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
- ✅ **Install dependencies** - Uses `npm ci` for consistent, clean installs
- ✅ **ESLint** - Checks code quality and style
- ✅ **Build** - Verifies production build succeeds
- ✅ **Bundle size** - Reports build output size
- ✅ **Tests** - Runs Vitest tests (currently optional until tests are written)
- ✅ **Artifacts** - Uploads build output for review

**What it catches:**
- Syntax errors
- Import issues
- ESLint violations
- Build failures
- Broken dependencies

#### 2. **Security Audit**

Checks for security vulnerabilities in dependencies.

**Steps:**
- ✅ **npm audit** - Scans for known vulnerabilities
- ✅ **Outdated packages** - Lists packages that need updates

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

### ✅ **Always Required (Blocks PR)**
- ESLint passes
- Production build succeeds

### ⚠️ **Optional (Warns but doesn't block)**
- Security audit (informational)
- Tests (until test suite is complete)
- Outdated packages (informational)

## Local Development

Before pushing, you can run these checks locally:

```bash
cd frontend

# Run all checks
npm run lint        # ESLint
npm run build       # Production build
npm run test        # Tests (when available)
npm audit           # Security check
```

## Configuration Files

- **ESLint**: `frontend/eslint.config.js`
- **Vite**: `frontend/vite.config.js`
- **Vitest**: `frontend/vitest.config.js`

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

**Cause:** Code doesn't meet style guidelines

**Solution:**
```bash
npm run lint          # See errors
npm run lint -- --fix # Auto-fix when possible
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

- 🔄 **Visual regression testing** - Screenshot comparisons
- 📊 **Code coverage** - Track test coverage percentage
- 🎨 **Lighthouse CI** - Performance and accessibility scores
- 📦 **Bundle analysis** - Detailed size breakdown
- 🔐 **License checking** - Verify dependency licenses
- 🌐 **E2E tests** - Playwright/Cypress integration

## Questions?

See the main workflow documentation at `.github/WORKFLOWS.md`
