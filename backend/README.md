# HOMEPOT Backend

This directory contains the Python backend service for the HOMEPOT Client.

## Structure

```text
backend/
|-- homepot/                # Main Python package
|   |-- app/                # FastAPI application
|   |-- push_notifications/ # Push notification services
|   |-- agents.py
|   |-- database.py
|   `-- ...
|-- tests/                  # Backend tests
|-- pyproject.toml          # Python project configuration
|-- requirements.txt        # Python dependencies
`-- README.md               # This file
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

## Agent API Contract (Pilot)

Use these endpoints for the Dealdio real-device flow:

- `POST /api/v1/agent/device-dna`
  Register a new device (or update existing device DNA).
- `POST /api/v1/agent/heartbeat`
  Update `last_heartbeat_at` for online/offline tracking.
- `POST /api/v1/agent/telemetry`
  Save one telemetry item or a bulk list.
- `GET /api/v1/agent/{device_id}/status`
  Get computed `ONLINE` or `OFFLINE` state.
- `POST /api/v1/devices/provision`
  Auto-provision a device from setup wizard input (`user_identity`, optional `sso_token`) and return (`device_id`, `api_key`) plus backward-compatible fields.

Note: existing legacy `POST /api/v1/agent/register` remains available for compatibility.

## Local IPC API (Agent)

When the real-device agent runs locally, UI apps can query:

- `GET http://127.0.0.1:8765/health`
- `GET http://127.0.0.1:8765/status`
- `GET http://127.0.0.1:8765/last-telemetry`
- `GET http://127.0.0.1:8765/ipc/status` (alias)
- `GET http://127.0.0.1:8765/ipc/last-telemetry` (alias)

The agent now publishes Device DNA to `POST /api/v1/agent/device-dna` and keeps IPC status synchronized with heartbeat/telemetry loops.

## Frozen Mock Contracts

Use these canonical payload files for UI mocks:

- `src/homepot/agent/mock_dna.json`
- `src/homepot/agent/mock_telemetry.json`

## Development

See the main project [README](../README.md) for complete development instructions.
