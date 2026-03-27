# Dealdio: Real Device Pilot & User App Preparations

**Owner:** Dealdio Engineering Team  
**Status:** In Progress  
**Objective:** Validate the "Hybrid Fleet" architecture, package the real device agent, and prepare the underlying backend and local APIs for the GetFudo User App implementation.

---

## Part 1: Core Agent Packaging (From Original Spec)

### 1.1 Dependency Isolation
*   Create a minimal `requirements-app.txt` containing only necessary libraries for the agent (e.g., `httpx`, `psutil`, `asyncio`).
*   Ensure full backend dependencies (`fastapi`, `sqlalchemy`) are excluded from the agent's footprint.

### 1.2 Enhanced Data Collection (Device DNA)
*   Update `real_device_agent.py` to collect static entries:
    *   **IP Address:** Local and WAN IP.
    *   **MAC Address:** Physical address of the primary interface.
    *   **OS Details:** OS Name and Version (e.g., "Ubuntu 22.04" or "Windows 11").
*   Send this payload on startup/registration and include it in the heartbeat.

### 1.3 Configuration Handling
*   Modify `real_device_agent.py` to accept configuration via a simple JSON file (`agent-config.json`) instead of relying solely on environment variables.
*   Required fields: `backend_url`, `device_id`, `api_key`, `site_id`.

### 1.4 Executable Generation
*   Use `pyinstaller` (or similar) to create standalone binaries for Linux and Windows to simplify deployment.

---

## Part 2: Preparatory Tasks for GetFudo Collaboration

### 2.1 Build the Agent's Local Inter-Process Communication (IPC)
*   Implement a local communication layer in `real_device_agent.py` (e.g., a lightweight local FastAPI server on `localhost` or a UNIX Domain Socket).
*   **Goal:** Allow GetFudo's Electron/React UI to query local device status without needing OS-level access.

### 2.2 Scaffold Backend Database & Endpoints for "Device DNA"
*   Update core backend (SQLAlchemy models) to store `os_details`, `mac_address`, and `wan_ip`.
*   Establish and document the `/api/v1/agent/telemetry` endpoints in Swagger/OpenAPI.

### 2.3 Extend the Setup Wizard Capabilities (Backend Auto-Provisioning)
*   Create a new backend endpoint (e.g., `POST /api/v1/devices/provision`) that accepts an SSO token/user identity and dynamically issues a `device_id` and `api_key`.
*   **Goal:** Replace manual provisioning for the User App.

### 2.4 Create "Agent Stubs" & Mock Payloads
*   Export canonical `mock_dna.json` and `mock_telemetry.json` representing exactly what the agent and backend will output.
*   **Goal:** Unblock GetFudo so they can mock their UI against frozen data contracts.

---

## Part 3: Pilot Deployment & Verification (From Original Spec)

*   **Manual Provisioning:** Register 5 new "Real Devices" (`physical_terminal`) in the web admin.
*   **Agent Installation:** Deploy the binaries and `agent-config.json` to 5 physical Linux/Windows machines.
*   **Service Setup:** Configure the agent as a system service (`systemd` / Windows Service).
*   **Verification:** Confirm Dashboard reflects Online status, real-time telemetry, Device DNA, and consistent heartbeats.
