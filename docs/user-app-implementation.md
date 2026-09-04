# User App Implementation Guide

## Overview
The HOMEPOT User App is a lightweight native client agent (acting as a "Digital Security Badge") designed to run continuously on employee devices (Android, Windows, macOS, Linux). It operates completely independently of the centralized web-based Admin Dashboard.

This implementation utilizes a **Hybrid Monolith** architecture: compiling a single shared React UI into native Desktop shells (via Electron) and Mobile shells (via Capacitor).

## Directory Setup
The frontend source code is isolated within the top-level `/user_app` directory to prevent any cross-contamination with the core Admin Dashboard (`/frontend`).

## Prerequisites
To develop the User App, ensure you have the following installed locally:
*   **Node.js**: v18+ (Node v20 LTS recommended)
*   **npm**: Standard package manager
*   *(Future)* Desktop build tools for Electron (e.g., MSVC on Windows, Xcode on macOS)
*   *(Future)* Android Studio / SDKs for building the mobile APK via Capacitor.

## Tech Stack
The foundational UI stack mirrors the Admin Dashboard to allow for seamless code reuse:
*   **Core**: React 19 + TypeScript
*   **Bundler**: Vite (SWC)
*   **Styling**: Tailwind CSS v3.4.x + Radix UI

## Getting Started Locally

Currently, the scaffolding can be run as a standard development web server:

```bash
# 1. Navigate to the application directory
cd user_app

# 2. Install required dependencies
npm install

# 3. Start the local development server (typically opens on port 5173)
npm run dev
```

## Implementation Phases
1. **Phase 1:** Web-based UI layout and scaffolding using Tailwind CSS and raw React components. *(merged)*
2. **Phase 2:** Wrapping the Vite build in **Electron** (for Desktop OS logic) and **Capacitor** (for Android logic). *(Electron shell + emulator bridge merged)*
3. **Phase 3:** Connecting the React context state to the local IPC network layer broadcasted by the underlying Python device agent. *(in progress — see PR tracker below)*

## User App — Device Communication Architecture

The User App **never communicates directly with devices**. It always routes through the Dashboard backend, using the device's own API credentials as an authentication proxy.

```
Technician ──► User App ──► Dashboard Backend ◄── Device Agent
                  │              ▲                    │
                  │         (X-Device-ID +       (heartbeat,
                  │          X-API-Key)         telemetry,
                  │              │               commands,
                  │              │               etc.)
                  │         backend authenticates
                  │         using device credentials
```

Every device-facing call in `user_app/src/services/api.ts` sends `deviceAuthHeaders(deviceId, apiKey)` — `X-Device-ID` and `X-API-Key` — to the backend. The backend authenticates the request with those credentials and returns the device's data. The User App is therefore a **credential proxy**: the technician's session delegates to the device's identity.

### Endpoints the User App calls

| Function | Endpoint | Purpose |
|---|---|---|
| `fetchDevice()` | `GET /devices/device/{id}` | Device record |
| `fetchDeviceStatus()` | `GET /agent/{id}/status` | Lifecycle + connectivity |
| `fetchDeviceMetrics()` | `GET /agent/{id}/metrics` | CPU / memory / disk |
| `fetchDeviceMetricsHistory()` | `GET /agent/{id}/metrics/history` | Metrics history |
| `fetchPermissions()` | `GET /devices/device/{id}/permissions` | What the technician can do |
| `updatePermissions()` | `PATCH /devices/device/{id}/permissions` | Grant / revoke permissions |
| `fetchPendingCommands()` | `GET /devices/pending` | Commands queued for the device |
| `ackCommand()` | `POST /devices/{id}/commands/{cid}/ack` | Acknowledge a command |
| `updateCommandStatus()` | `PUT /devices/{id}/commands/{cid}/status` | Report command result |
| `verifyDeviceCredentials()` | `GET /devices/device/{id}/permissions` (probe) | Validate stored credentials |
| `unpairDevice()` | `DELETE /devices/device/{id}` | Unpair a device |

### Credential storage

The User App stores device credentials via an abstract `CredentialStorage` interface (`user_app/src/services/credentialStorage.ts`), with platform-specific implementations:

| Platform | Implementation | Storage location |
|---|---|---|
| Browser / simulation | `SimulationStorage` | `sessionStorage` + `localStorage` |
| Linux (Electron/Tauri) | `LinuxFileStorage` | `~/.homepot/credentials` (mode `0600`) |
| Electron (macOS / Windows) | `ElectronStorage` | Native IPC bridge to main process |
| Windows (future) | `WindowsCredManager` | *(placeholder — falls back to `LinuxFileStorage`)* |
| Android (future) | `AndroidKeystore` | *(placeholder — falls back to `SimulationStorage`)* |

Expanding to a new device/platform means implementing the corresponding `CredentialStorage` backend. The API layer stays the same — every platform hits the same Dashboard endpoints with the same `deviceAuthHeaders`.

## PR Tracker

Single source of truth for User App pull requests. Each row links the PR, its branch, and what it delivers against the emulator/backend feature set. Emulator/backend work that the User App UI builds on is listed for reference.

### Prerequisites (merged — emulator/backend)

| PR | Branch | Scope | Status |
|----|--------|-------|--------|
| [#250](https://github.com/brunel-opensim/homepot-client/pull/250) | `feat/live-device-reporting` | Live device reporting via POS emulator (logs, audit, jobs, alerts, telemetry) | merged |
| [#251](https://github.com/brunel-opensim/homepot-client/pull/251) | `feat/emulator-command-response` | Emulator handles status requests and composed push commands | merged |
| [#252](https://github.com/brunel-opensim/homepot-client/pull/252) | `feat/emulator-logs` | Emulator runs in background with `logs/emulator.log` + stop script | merged |
| [#253](https://github.com/brunel-opensim/homepot-client/pull/253) | `fix/emulator-start-default-config` | Fail fast when default config has placeholder site/key | merged |
| [#254](https://github.com/brunel-opensim/homepot-client/pull/254) | `feat/emulator-permissions` | Emulator permission emulation (consent modes + `request_permission`) | merged |

### Planned User App PRs

| # | Branch (proposed) | Scope | Status |
|---|-------------------|-------|--------|
| 1 | `feat/user-app-service-refactor` | Route views through `services/api.ts` (currently bypassed with raw `fetch`); fix `AppContext` `isProvisioned` bug (reads `homepot_token`, never written by `SimulationStorage`); fix `ClaimDevice` response-shape handling | planned |
| 2 | `feat/user-app-live-dashboard` | Real telemetry on HomeDashboard via `GET /devices/device/{id}/metrics` (CPU/mem/disk/net/uptime); real heartbeat from `last_heartbeat_at`; replace hardcoded gauge values | planned |
| 3 | `feat/user-app-permission-request` | `request_permission` consent prompt (accept/deny operator requests); admin-override flow | planned |
| 4 | `feat/user-app-activity-screens` | Error Logs screen via `GET /agent/{device_id}/logs` (device-auth, own-logs only). Audit/jobs/alerts/push stay on the operator Dashboard to keep the User App lightweight | planned |
| 5 | `feat/user-app-live-updates` | *(optional)* WebSocket live updates (`/ws/status`) | optional |

Update this table as PRs are opened/merged so the tracker stays current.
