# AGENTS.md — instructions for AI agents working in this repository

This file is read by AI coding agents (OpenCode, Copilot, etc.) before they
make changes. Follow these rules for every change, and run the pre-PR checklist
before opening a pull request.

## Repository layout

- `backend/` — FastAPI backend (Python). Source under `backend/src/homepot/`.
- `frontend/` — React (Vite) web app.
- `user_app/` — Windows/macOS user app.
- `ai/` — agent, tools, gates, analytics service.
- `docs/` — MkDocs documentation.
- `backend/tests/` — pytest suite.

## Non-negotiable conventions

1. **No emoji status markers** in repository docs. Use plain words (Done/Partial/Open).
2. **No commercial LLM API keys in git.** Keys come from env / secret manager; demo secrets are server-side only.
3. **Server tracks GitHub `main`.** The assistant opens PRs; the user merges. Do not merge PRs yourself unless explicitly told "please go ahead".
4. **Ask before removing pages.** The Devices page stays.
5. **Command templates must not claim actions not performed.** Final Payload Preview shows the exact request including `action`/`command_type`.
6. **Technicians are not genuine admins** but see all sites (`unified_fleet_access`).
7. **Document pros/cons** when introducing dev-only access changes.

## Pre-PR quality gates (run ALL before opening a PR)

### Backend (touched files)

```bash
cd backend
# Lint + format
../.venv/bin/black --check <touched files>
../.venv/bin/isort --check-only <touched files>
../.venv/bin/flake8 <touched files>

# Type check (whole package)
../.venv/bin/mypy --config-file=backend/mypy.ini backend/src/homepot/

# Tests
../.venv/bin/python -m pytest <relevant test files> -n 0 -p no:cacheprovider --no-cov -q
```

Rules:
- Every new public function needs a docstring (flake8 D103).
- No unused imports (F401).
- mypy must pass on `backend/src/homepot/` (transitively checks `ai/`).

### Frontend (touched files)

```bash
cd frontend
npm run format:check
npm run lint
npm test
npm run build
```

### Docs

```bash
mkdocs build --strict
```

### General

- New features need tests (backend and/or frontend).
- Update `docs/ai-delegation-plan.md` §17.7 status matrix when closing a gap.
- Keep PRs focused: one gap / one feature per PR.
- Commit messages: `<type>(<scope>): <description>` (see CONTRIBUTING.md).

## CI checks that must pass

The following GitHub Actions jobs are required on every PR:
- Code Quality (black, isort, flake8, mypy) — Python 3.11 & 3.12
- Test Suite (pytest) — ubuntu/windows/macos
- Secret Scanning
- Security Vulnerability Audit
- Verify MkDocs Build
- User App Quality Checks (if user_app touched)

If a check fails, fix the root cause — do not disable or skip checks.

## Deployment (after merge)

Server (ssh demouser, deploy root `/var/www/homepot.cabera.com`):
```bash
cd /var/www/homepot.cabera.com
git pull --ff-only origin main
sudo -n /usr/bin/systemctl stop homepot-api
sudo -n /usr/bin/systemctl start homepot-api
```
Frontend: build to `/tmp/homepot-dist-new`, swap `dist`, preserve `dist/downloads`, move old to `~/frontend-dist-rollback-<ts>`.

## Do not

- Push directly to `main`.
- Merge PRs unless the user explicitly says "please go ahead".
- Remove pages (Devices page stays).
- Commit API keys or secrets.
- Use emoji status markers in docs.
PYEOF
echo "written"