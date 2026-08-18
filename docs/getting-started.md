# Getting Started with HOMEPOT

Welcome to **HOMEPOT** (Homogenous Cyber Management of End-Points and OT). This guide provides a straightforward path to getting the system up and running using our automated scripts.

## Prerequisites

Before starting, ensure your system meets the following requirements:

1.  **Operating System**: Linux (Ubuntu 22.04+ recommended) or macOS.
2.  **Git**: Installed and configured.
3.  **Package Manager**:
    *   **macOS**: [Homebrew](https://brew.sh/) is required for automated installation of dependencies.
    *   **Linux**: `apt` (for Ubuntu/Debian).
4.  **Python**: Version 3.11 or higher.
5.  **Node.js**: Version v22.
    *   *(Note: Our install script will attempt to install this automatically if missing.)*
6.  **Ollama** (Required for AI Features):
    *   **Option A (Automated)**: Run `./scripts/setup-ollama.sh` (uses Homebrew on Mac).
    *   **Option B (Manual)**: Install from [ollama.com](https://ollama.com) and pull the `qwen3:4b` model manually.

## Quick Start Guide

Follow these three steps to launch the complete HOMEPOT system.

### Step 1: Install Dependencies

Make scripts executable and run the installer. This script sets up the Python virtual environment, installs backend/AI dependencies, and automatically installs/configures Node.js and frontend dependencies.

```bash
chmod +x scripts/*.sh
./scripts/install-backend.sh
```

> **Note**: If you haven't installed Ollama yet, run the AI setup script next. On macOS, this will use Homebrew to install Ollama and pull the required model.
> ```bash
> ./scripts/setup-ollama.sh
> ```

### Step 2: Initialize Database

Initialize the PostgreSQL database with the required schema and demo data. This script detects your local PostgreSQL installation (via Homebrew on macOS or system packages on Linux) and ensures the service is running before creating the database.

```bash
./scripts/init-postgresql.sh
```

> **Note**: This setup uses a local PostgreSQL instance and does not require Docker.


### Step 3: Start the Application

Use the following command to ensure any previous instances are stopped before starting the new session. This launches both the backend API and the frontend dashboard.

```bash
./scripts/stop-dashboard.sh && ./scripts/start-dashboard.sh
```

---

## What's Next?

Once the system is running, you can access:

- **Dashboard**: [http://localhost:5173](http://localhost:5173)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

For detailed development information, refer to the [Development Guide](development-guide.md).

## Three Test Integration Modes

The system supports **three** device modes. **Test technicians should know which mode they are running**, because each one produces telemetry through a different path:

1. **Simulation** — The backend's in-process agent simulator (`ENABLE_AGENT_SIMULATION=true`, the default in `backend/.env`) starts a simulated agent for every active POS/IoT device on startup. It writes heartbeats, health checks, and metrics directly to the database, and flips devices from `pending` to `active`. No external process is needed.
2. **Emulation** — Standalone emulator processes (`./scripts/start-emulator.sh`) authenticate against the backend and behave like real hardware over the agent API (device DNA, heartbeat, telemetry, command polling). Use this for end-to-end testing of the device lifecycle and User App without physical hardware. See [Device Emulators](device-emulators.md).
3. **Real Devices** — Physical devices running the HOMEPOT agent (or the Dealdio integration) talk to the backend over the network. See the [Agent API Contract](getfudo-preparatory-tasks.md#3-api-contract-summary) for the endpoint summary.

> **Tip for test technicians:** if Simulation is disabled (`ENABLE_AGENT_SIMULATION=false`), the **Data Collection** page cannot be started, devices stay `pending`, and telemetry appears empty. Keep `ENABLE_AGENT_SIMULATION=true` to collect data via simulation.

## Starting & Stopping All Services

The HOMEPOT platform runs **five** independent services. This section documents the
clean start/stop cycle, which doubles as a smoke test to catch startup issues early.

| Service | Log file (`logs/`) | PID file (`logs/`) | Start command | Stop command |
|---------|--------------------|--------------------|---------------|--------------|
| **Backend** (API :8000) | `backend.log`, `backend.out` | `backend.pid` | `./scripts/start-dashboard.sh` | `./scripts/stop-dashboard.sh` |
| **Frontend** (Vite :5173) | `frontend.log` | `frontend.pid` | `./scripts/start-dashboard.sh` | `./scripts/stop-dashboard.sh` |
| **AI / LLM** (Ollama :11434) | `ai.log` | `ai.pid` | `./scripts/setup-ollama.sh` | n/a (see note) |
| **Emulator** (POS terminal) | `emulator.log` | `emulator.pid` | `./scripts/start-emulator.sh` | `./scripts/stop-emulator.sh` |
| **User App** (Electron agent) | `userapp.log` | `userapp.pid` | `./scripts/start-userapp.sh` | `./scripts/stop-userapp.sh` |

### Full Restart (verified smoke test)

1.  **Stop all services** — terminate the dashboard pair, any emulator, and the
    User App. (Ollama/AI is left running if it was already active on :11434.)

    ```bash
    ./scripts/stop-dashboard.sh          # backend + frontend
    ./scripts/stop-emulator.sh           # any running emulator
    ./scripts/stop-userapp.sh            # Electron User App
    ```

2.  **Verify nothing is left on the ports:**

    ```bash
    ss -tlnp | grep -E '8000|5173|11434'   # expect no listeners (or only 11434 = ollama)
    ```

3.  **Start the core platform** (backend + frontend):

    ```bash
    ./scripts/start-dashboard.sh
    ```

4.  **Start optional services** as needed:

    ```bash
    ./scripts/setup-ollama.sh             # AI / LLM service
    ./scripts/start-emulator.sh --emulator linux \
        --site-id SITE-P7K5-BPHZ \
        --bootstrap-key <key> --device-name demo-pos-1
    ./scripts/start-userapp.sh            # Electron User App
    ```

5.  **Verify every service**:

    ```bash
    curl -s -o /dev/null -w 'backend: %{http_code}\n' http://127.0.0.1:8000/api/v1/health
    curl -s -o /dev/null -w 'frontend: %{http_code}\n' http://127.0.0.1:5173
    curl -s -o /dev/null -w 'login: %{http_code}\n' \
      -X POST http://127.0.0.1:8000/api/v1/auth/login \
      -H 'Content-Type: application/json' \
      -d '{"email":"admin@homepot.com","password":"homepot_dev_password"}'
    ```

    Every command should return `200`, and each service should have a matching
    `.log` / `.pid` pair in `logs/`.

> **Troubleshooting notes from a real smoke test:**
>
> - **Ollama running as a different OS user** (e.g. systemd `ollama` service): `lsof` on
>   the port returns nothing under your user, so `setup-ollama.sh` probes the Ollama
>   HTTP API (`/api/version`) and falls back to `pgrep` — it will reuse the existing
>   instance and write its real PID to `ai.pid`. A stale/dead PID in `ai.pid` usually
>   means the instance could not bind the port.
> - **"Request failed with status code 500" at login** almost always means the
>   **backend is not running** — Vite returns a proxy 500. Check
>   `curl http://127.0.0.1:8000/api/v1/health` first.
> - **Clean log reset:** delete everything in `logs/` (except `README.md`) before a
>   fresh run to confirm each service recreates its files.

## Troubleshooting

### Login Page Returns 500 / Connection Refused (ECONNREFUSED)

If you encounter a `500` error or "Connection Refused" when attempting to log in, it is likely that the Vite development server proxy is pointing to the wrong backend port.

*   **Symptoms**: You see `Error: connect ECONNREFUSED 127.0.0.1:8001` in the frontend logs or terminal when trying to hit `/api/v1/auth/login`.
*   **Fix**: Update the `target` port in the `frontend/vite.config.js` proxy settings to point to port `8000` (the default backend port).
    ```javascript
    export default defineConfig({
      // ...
      server: {
        proxy: {
          '/api': {
            target: 'http://127.0.0.1:8000', // Ensure this points to port 8000
            // ...
          },
        },
      },
    });
    ```
