# Transitioning to Real Device Monitoring

## Overview

HOMEPOT Client began as a simulation-first platform to validate the dashboard and analytics capabilities without requiring physical hardware. As the system matures, we are transitioning from pure simulation to real-time monitoring of physical devices (POS terminals, servers, IoT devices).

This document outlines the architecture of this transition, the tools involved, and the roadmap for full production readiness.

## The "Simulation-First" Architecture

Initially, HOMEPOT relied entirely on mock data to drive the user interface.

### 1. Agent Simulator (`backend/src/homepot/agents.py`)
*   **Role:** Maintains the state of fake devices in memory.
*   **Behavior:** Randomly generates uptime, simulates configuration downloads, and mimics device failures.
*   **Limitation:** Data is ephemeral and randomized; it does not reflect reality.

### 2. Traffic Generator (`backend/utils/generate_traffic.py`)
*   **Role:** A development utility to populate the database with "User Activity" and "Application Errors."
*   **Usage:** Essential for demos and verifying the analytics pipeline.
*   **Status:** Will remain useful for load testing and development but is not part of the production ingestion pipeline.

## The "Hybrid" Architecture (Current State)

We have introduced the capability to monitor real devices alongside simulated ones. This allows developers to use their own machines (e.g., WSL2 instances) as live assets in the HOMEPOT system.

### 1. Real Device Agent (`backend/utils/real_device_agent.py`)
*   **Role:** A lightweight Python script that runs on a physical device or server.
*   **Function:**
    *   **Registration:** Automatically registers the device with the backend (e.g., `wsl-device-workstation`).
    *   **Telemetry:** Uses `psutil` to collect real CPU, Memory, Disk, and Network metrics.
    *   **Ingestion:** Pushes data to `POST /api/v1/analytics/device-metrics`.
*   **Usage:**
    ```bash
    source .venv/bin/activate
    python backend/utils/real_device_agent.py
    ```

### 2. Backend Support
*   **Endpoint:** `POST /api/v1/analytics/device-metrics` accepts telemetry from both simulated and real agents.
*   **Data Model:** The `DeviceMetrics` table stores performance data regardless of its source.

## Roadmap to Production

### Phase 1: Hybrid (Completed)
*   Create `real_device_agent.py` for Linux/WSL.
*   Enable backend to accept external metrics.
*   Visualize real data on the dashboard alongside simulated data.

### Phase 2: Device Authentication (Completed)
*   **API Key Generation:** When a device is registered via `POST /api/v1/devices/sites/{site_id}/devices`, the backend generates a secure, unique API Key.
*   **Secure Storage:** The API Key is returned *once* upon creation. The backend stores only a hash of the key.
*   **Authentication Headers:** Real devices must authenticate requests using:
    *   `X-Device-ID`: The device's unique identifier.
    *   `X-API-Key`: The secret key provided at registration.

### Phase 3: Remote Command Execution (In Progress)
*   **Command Queuing:** Admins or automated systems can queue commands (e.g., `REBOOT`, `UPDATE_CONFIG`) for specific devices via `POST /api/v1/devices/{device_id}/commands`.
*   **Command Retrieval:** Devices periodically poll `GET /api/v1/devices/pending` to fetch queued commands.
*   **Status Updates:** Devices report command execution results (Success/Failure) back to the server (Coming Soon).

## Implementation Details

### Device Registration
To register a new real device:
1.  **Endpoint:** `POST /api/v1/devices/sites/{site_id}/devices`
2.  **Payload:**
    ```json
    {
      "device_id": "pos-terminal-001",
      "name": "Main Checkout POS",
      "device_type": "pos_terminal",
      "ip_address": "192.168.1.100"
    }
    ```
3.  **Response:** Returns the `api_key`. **Save this immediately.**

### Polling for Commands
The device agent should run a loop (e.g., every 60 seconds):
1.  **Endpoint:** `GET /api/v1/devices/pending`
2.  **Headers:**
    *   `X-Device-ID`: `pos-terminal-001`
    *   `X-API-Key`: `your_secret_api_key`
3.  **Action:** If a command is received, execute it and report status.
*   **Secure Registration:** Devices now register once and receive a unique, high-entropy API Key.
*   **Token Storage:** The agent securely stores the key locally (e.g., `.device_api_key`).
*   **Authenticated Requests:** All telemetry and heartbeat requests must include `X-API-Key` and `X-Device-ID` headers.
*   **Backend Verification:** The backend verifies the hash of the API key against the database before accepting metrics.

### Phase 3: Smart Management (Next Steps)
*   **Command Queue:** Implement MQTT or Redis-based command queue so the backend can send commands (e.g., "Restart") to real devices.
*   **Smart Switching:** The system automatically detects if a device is "Real" or "Simulated" and adjusts the UI accordingly.
*   **OTA Updates:** Implement real file transfer for configuration updates to physical devices.

## Security Architecture

With the completion of Phase 2, the communication between the Real Device Agent and the Backend is secured via a custom API Key mechanism.

1.  **Registration:**
    *   Agent sends `POST /devices/sites/{site_id}/devices` with device details.
    *   Backend generates a 32-byte secure token, hashes it (bcrypt), stores the hash, and returns the **plaintext key** to the agent.
    *   **Crucial:** The plaintext key is shown *only once*.

2.  **Storage:**
    *   The agent saves the key to a local file (default: `.device_api_key`).
    *   On subsequent restarts, the agent reads this file instead of re-registering.

3.  **Authentication:**
    *   Every request to protected endpoints (e.g., `/analytics/device-metrics`) requires:
        *   `X-Device-ID`: The public identifier of the device.
        *   `X-API-Key`: The secret token.
    *   The backend looks up the device by ID and verifies the provided key against the stored hash.

## Summary

| Feature | Simulation Mode | Real Device Mode |
| :--- | :--- | :--- |
| **Source** | `agents.py` (Random) | `real_device_agent.py` (psutil) |
| **Identity** | Seeded in DB | Auto-registered via API |
| **Connectivity** | In-Memory | HTTP / REST |
| **Use Case** | Demos, UI Dev | Production Monitoring |


