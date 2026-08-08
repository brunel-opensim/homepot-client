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

## Test Integration Modes

The backend supports **three** device modes. Test technicians must know which mode they are running, because each one produces telemetry through a different path:

| Mode | How it works | Telemetry source | When to use |
|------|--------------|------------------|-------------|
| **1. Simulation** | The backend's built-in `DeviceAgentSimulator` (see `homepot/agents.py`) runs **in-process**. On startup it discovers active POS/IoT devices and starts a simulated agent per device, sending heartbeats, health checks, and metrics. Controlled by `ENABLE_AGENT_SIMULATION` (default `true` in `backend/.env`). | In-process simulator writes directly to the database. Devices become `lifecycle_state=active` when the agent starts. | Local demos, dashboards, AI training-data collection with no external processes. |
| **2. Emulation** | Separate standalone Python processes (see `emulators/` and `scripts/start-emulator.sh`) authenticate against the backend and behave like a real device via the agent API (device DNA, heartbeat, telemetry, command polling). | HTTP agent endpoints from an external process. | End-to-end testing of the full device lifecycle + User App without physical hardware. |
| **3. Real Devices** | Physical devices run the HOMEPOT agent (or the Dealdio integration) and talk to the backend over the network (see "Agent API Contract" below, e.g. `device-dna`, `heartbeat`, `telemetry`). | Real HTTP traffic from a device. | Production/field validation, acceptance testing. |

> **Important for test technicians:** if `ENABLE_AGENT_SIMULATION` is unset or `false`, Simulation mode is disabled and the **Data Collection** page cannot be started, so devices stay `pending` and telemetry appears empty. To collect data via simulation, keep `ENABLE_AGENT_SIMULATION=true` — e.g. `ENABLE_AGENT_SIMULATION=true uvicorn homepot.app.main:app --reload`.

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
