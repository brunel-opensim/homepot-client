# HOMEPOT Scripts

## Website Management

### `start-complete-website.sh`

Starts the complete HOMEPOT website with backend and frontend.

**Usage:**
```bash
./scripts/start-complete-website.sh
```

**What it does:**
1. Checks prerequisites (Python, Node.js, PostgreSQL)
2. Verifies ports 8000 and 5173 are available
3. Activates Python virtual environment (root `venv/`)
4. Starts backend server on http://localhost:8000
5. Starts frontend dev server on http://localhost:5173
6. Opens website in default browser

**Logs:**
- Backend: `logs/backend.log`
- Frontend: `logs/frontend.log`

**PIDs:**
- Backend: `logs/backend.pid`
- Frontend: `logs/frontend.pid`

### `stop-website.sh`

Stops both backend and frontend servers.

**Usage:**
```bash
./scripts/stop-website.sh
```

**What it does:**
1. Kills backend process (port 8000)
2. Kills frontend process (port 5173)
3. Cleans up PID files

## Environment Management

### `activate-homepot.sh`

Activates the Python virtual environment and sets up the development environment.

**Usage:**
```bash
source scripts/activate-homepot.sh
```

**What it does:**
1. Activates the Python virtual environment at `venv/`
2. Sets environment variables for development
3. Prepares the shell for backend development

## Important Notes

### Virtual Environment
- The project uses a **root-level virtual environment** at `venv/`
- Do NOT use `backend/venv/` (old structure, no longer used)
- Always activate with: `source venv/bin/activate` or use `activate-homepot.sh`

### bcrypt Compatibility
- The project requires `bcrypt==4.1.3` for authentication to work
- This is pinned in `backend/requirements.txt`
- Version 5.x has breaking changes with `passlib`

### PostgreSQL Database
- Backend requires PostgreSQL to be running
- Connection details in `backend/.env` or environment variables
- Default: `postgresql://homepot_user:homepot_dev_password@localhost/homepot_db`

## Troubleshooting

### "ModuleNotFoundError: No module named 'homepot'"
**Solution:** Install the package in editable mode:
```bash
cd backend
pip install -e .
```

### "Authentication failed" or "500 error on signup"
**Solution:** Verify bcrypt version:
```bash
pip show bcrypt  # Should show 4.1.3
pip install bcrypt==4.1.3  # If not
```

### Ports already in use
**Solution:** Stop existing services:
```bash
./scripts/stop-website.sh
# Or manually:
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9
```

### PostgreSQL not running
**Solution:** Start PostgreSQL service:
```bash
sudo systemctl start postgresql  # Linux systemd
# Or:
sudo service postgresql start    # Linux sysvinit
# Or:
brew services start postgresql   # macOS Homebrew
```

## For Frontend Developers

If you're working on the frontend UI/UX:

1. **Start the backend first:**
   ```bash
   cd backend
   source ../venv/bin/activate
   python -m uvicorn homepot.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Then start frontend in another terminal:**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Access the website:**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

4. **Test credentials:**
   - Email: `test@homepot.com`
   - Password: `Test123!`
   - Role: ENGINEER

## Analytics Validation

### `run_validation_test.sh`

Comprehensive validation of the analytics infrastructure. Automatically starts the backend, runs validation tests, and reports results.

**Usage:**
```bash
./scripts/run_validation_test.sh
```

**What it does:**
1. Starts backend server on http://localhost:8000
2. Authenticates test user
3. Tests user activity tracking (page views, clicks, searches)
4. Verifies automatic API request logging
5. Queries and displays collected analytics data
6. Shows summary of infrastructure status
7. Displays backend logs
8. Cleans up (stops backend)

**Validates:**
- Authentication endpoint
- User activity logging (`POST /api/v1/analytics/user-activity`)
- Automatic API request logging (middleware)
- Query endpoints (`GET /api/v1/analytics/user-activities`, `/api/v1/analytics/api-requests`)
- Database write operations
- JSON response formatting

**Use cases:**
- Pre-deployment verification
- Bug hunting and debugging
- Demonstrating analytics functionality
- Continuous integration testing

### `validate_analytics.py`

Python script for standalone analytics validation (called by `run_validation_test.sh`).

**Usage:**
```bash
# Assumes backend is already running on port 8000
python3 scripts/validate_analytics.py <email> <password>

# Example:
python3 scripts/validate_analytics.py analytics-test@example.com testpass123
```

## See Also

- [Complete Website Setup Guide](../docs/complete-website-setup.md) - Full setup instructions
- [Website Testing Guide](../docs/website-testing-guide.md) - Testing checklist
- [Development Guide](../docs/development-guide.md) - General development info
