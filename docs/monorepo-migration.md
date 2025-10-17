# Monorepo Structure Migration

This document describes the migration to a monorepo structure for better organization and scalability.

## New Structure

```
homepot-client/
├── backend/                     # Python backend (FastAPI)
│   ├── homepot_client/         # Main Python package
│   ├── tests/                  # Backend tests
│   ├── pyproject.toml         # Python project configuration
│   └── requirements.txt       # Python dependencies
│
├── frontend/                    # React frontend (Vite + React)
│   ├── src/                    # Frontend source code
│   ├── public/                 # Static assets
│   └── package.json           # npm dependencies
│
├── ai/                         # AI/LLM services (future)
│   ├── models/                # Trained models
│   ├── services/              # AI service layer
│   └── README.md
│
├── docs/                       # Shared documentation
├── scripts/                    # Utility scripts
├── data/                       # Data directory
├── .github/                    # CI/CD workflows
├── docker-compose.yml         # Multi-service orchestration
└── README.md                  # Main project documentation
```

## Changes Made

### Directory Moves

1. **Backend:**
   - `src/` → `backend/homepot_client/`
   - `tests/` → `backend/tests/`
   - `pyproject.toml` → `backend/pyproject.toml`
   - `requirements.txt` → `backend/requirements.txt`
   - `mypy.ini` → `backend/mypy.ini`

2. **Frontend:**
   - `homepot-frontend/` → `frontend/`

3. **AI (New):**
   - Created `ai/` directory for future ML/LLM services

### File Updates

- `backend/pyproject.toml`: Updated paths for packages, tests, and coverage
- `scripts/*.sh`: Updated to reference new paths
- Documentation: Updated references to new structure

## Benefits

1. **Clear Separation**: Backend, frontend, and future AI services are clearly separated
2. **Scalability**: Easy to add new services (mobile apps, AI services, etc.)
3. **Independent Development**: Each service can be developed and deployed independently
4. **Better Organization**: Follows industry best practices for full-stack projects
5. **Future-Ready**: Prepared for AI/LLM integration

## Migration for Developers

### Backend Development

```bash
cd backend
pip install -e ".[dev]"
pytest
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

### Full Stack Development

Use docker-compose from the root:

```bash
docker-compose up
```

## CI/CD Updates

GitHub Actions workflows updated to reflect new paths:
- Python tests now run from `backend/`
- Frontend tests now run from `frontend/`
- Scripts updated to work with new structure

## Questions?

See the main [README.md](../README.md) or contact the development team.
