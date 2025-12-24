# Running HOMEPOT Locally - Monorepo Guide

This guide explains how to run HOMEPOT locally after the monorepo restructuring.

## Overview

The repository is now organized as a monorepo with three main directories:

- **`backend/`** - Python FastAPI application (formerly `src/`)
- **`frontend/`** - React application (formerly `homepot-frontend/`)
- **`ai/`** - Future AI/LLM services (placeholder)

## Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher (for frontend)
- Git
- Virtual environment tool (venv, conda, etc.)

## Backend Setup

### 1. Create and Activate Virtual Environment

```bash
# From the repository root
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
# Install Python dependencies
cd backend
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Install Package in Editable Mode

```bash
# Still in backend/ directory
pip install -e .
```

This installs `homepot-client` in development mode, allowing you to make changes without reinstalling.

### 4. Initialize Database

```bash
# From repository root
./scripts/init-postgresql.sh
```

This creates the PostgreSQL database `homepot_db` with demo data (3 sites, 12 devices).

### 5. Start the Backend Server

```bash
# Option 1: Using Python module
python -m uvicorn homepot.main:app --reload --host 0.0.0.0 --port 8000

# Option 2: Using uvicorn command directly (if in PATH)
uvicorn homepot.main:app --reload --host 0.0.0.0 --port 8000
```

The `--reload` flag enables auto-restart on code changes (development mode).

### 6. Verify Backend is Running

Open your browser or use curl:

```bash
# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs  # or visit in browser
```

The FastAPI automatic documentation at `/docs` provides an interactive interface to test all endpoints.

## Frontend Setup

### 1. Install Node Dependencies

```bash
# From repository root
cd frontend
npm install
```

### 2. Start Development Server

```bash
npm run dev
```

The frontend will run on `http://localhost:5173` and connect to the backend on port 8000.

### 3. Build for Production

```bash
npm run build
```

Production files will be in `frontend/dist/`.

## Working with the Monorepo

### Directory Structure

```
homepot-client/
├── backend/
│   ├── homepot/        # Application code
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app entry point
│   │   ├── cli.py             # Command-line interface
│   │   ├── models.py          # Data models
│   │   ├── database.py        # Database setup
│   │   ├── config.py          # Configuration
│   │   └── app/               # FastAPI app components
│   ├── tests/                 # Backend tests
│   ├── pyproject.toml         # Python package config
│   ├── requirements.txt       # Dependencies
│   └── README.md              # Backend-specific docs
├── frontend/
│   ├── src/                   # React components
│   ├── public/                # Static assets
│   ├── package.json           # Node dependencies
│   └── vite.config.js         # Vite configuration
├── ai/
│   └── README.md              # Future AI services
├── docs/                      # Project documentation
├── scripts/                   # Utility scripts
└── README.md                  # Main project README
```

### Running Tests

#### Backend Tests

```bash
cd backend
pytest                             # Run all tests
pytest tests/test_client.py        # Run specific test file
pytest -v                          # Verbose output
pytest --cov=homepot        # With coverage
```

#### Frontend Tests

```bash
cd frontend
npm test                        # Run tests
npm run test:coverage          # With coverage
```

### Code Quality Checks

From the repository root:

```bash
# Run all validation checks
./scripts/validate-workflows.sh

# Individual checks
cd backend
black homepot tests     # Format code
isort homepot tests     # Sort imports
flake8 homepot tests    # Linting
bandit -r homepot       # Security checks
mypy homepot            # Type checking
```

### Using Scripts

The monorepo includes helpful scripts in `scripts/`:

```bash
# Initialize PostgreSQL database
./scripts/init-postgresql.sh

# Run POSDummy simulator
./scripts/run-pos-dummy.sh

# Check repository health
./scripts/check-repo-health.sh

# Build documentation
./scripts/build-docs.sh
```

## Common Development Workflows

### Making Backend Changes

1. Ensure virtual environment is activated: `source venv/bin/activate`
2. Navigate to backend: `cd backend`
3. Make your changes in `homepot/`
4. Run tests: `pytest`
5. Check code quality: `black . && flake8 .`
6. The server will auto-reload if running with `--reload`

### Making Frontend Changes

1. Ensure dev server is running: `npm run dev`
2. Navigate to frontend: `cd frontend`
3. Make changes in `src/`
4. Vite will hot-reload automatically
5. Check for errors in browser console

### Adding Dependencies

#### Backend

```bash
cd backend
pip install <package>
pip freeze > requirements.txt  # Update requirements
```

#### Frontend

```bash
cd frontend
npm install <package>           # Adds to package.json automatically
```

## Troubleshooting

### Backend Won't Start

**Problem**: `ModuleNotFoundError: No module named 'homepot'`

**Solution**: Install the package in editable mode:
```bash
cd backend
pip install -e .
```

### Database Issues

**Problem**: Database connection errors

**Solution**: Ensure PostgreSQL is running and database exists:
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Reinitialize if needed
./scripts/init-postgresql.sh
```

### Port Already in Use

**Problem**: `Address already in use` error

**Solution**: Kill the existing process:
```bash
# Find process using port 8000
lsof -i :8000
kill -9 <PID>

# Or use a different port
python -m uvicorn homepot.main:app --port 8001
```

### Frontend Can't Connect to Backend

**Problem**: Network errors in frontend

**Solution**: Verify backend is running and CORS is configured:
```bash
curl http://localhost:8000/health
```

Check `backend/src/homepot/main.py` for CORS settings.

## Docker Setup (Alternative)

To run the entire stack with Docker:

```bash
# From repository root
docker-compose up --build
```

This starts both backend and frontend in containers.

## Environment Variables

Create a `.env` file in the backend directory:

```env
# Backend Configuration
DATABASE__URL=postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db
SECRET_KEY=your-secret-key-here
DEBUG=true

# Optional: External Services
MQTT_BROKER=localhost
MQTT_PORT=1883
```

## Next Steps

- Review the [Development Guide](development-guide.md) for coding standards
- Check [Database Guide](database-guide.md) for schema details
- See [API Documentation](http://localhost:8000/docs) when server is running
- Read [Monorepo Migration Guide](monorepo-migration.md) for architecture details

## Questions?

If you encounter issues not covered here:

1. Check the [GitHub Issues](https://github.com/brunel-opensim/homepot-client/issues)
2. Review recent commits for changes
3. Ask the team in Slack/Discord
4. Consult the [Collaboration Guide](collaboration-guide.md)
