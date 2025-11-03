# HOMEPOT Backend

This directory contains the Python backend service for the HOMEPOT Client.

## Structure

```
backend/
├── homepot/          # Main Python package
│   ├── app/                 # FastAPI application
│   ├── push_notifications/  # Push notification services
│   ├── agents.py
│   ├── database.py
│   └── ...
├── tests/                   # Backend tests
├── pyproject.toml          # Python project configuration
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Quick Start

### Installation

From the project root:

```bash
cd backend
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Running the Server

```bash
uvicorn homepot.app.main:app --reload
```

## Development

See the main project [README](../README.md) for complete development instructions.
