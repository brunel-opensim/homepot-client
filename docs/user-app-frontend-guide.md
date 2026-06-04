# HOMEPOT User App — Frontend Developer Guide

**Author:** Radhakrishnan (GetFudo)
**Date:** 2026-05-14
**Branch:** feature/user-app-frontend-scaffold (PR #149)

---

## 1. Overview

The HOMEPOT User App is a lightweight "Digital Security Badge" installed on employee endpoint devices. It gives employees real-time visibility of their device security status and gives them local control over what the Admin Dashboard can access.

This guide covers the frontend only — the React UI layer. The background Python daemon is built by the Dealdio team separately.

---

## 2. Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| React | 19 | UI framework |
| TypeScript | 5.9 | Type safety |
| Vite (SWC) | 8 | Build tool and dev server |
| Tailwind CSS | 3.4 | Styling |
| Radix UI | Latest | Accessible UI primitives (toggles, progress) |
| PostCSS | 8.5 | CSS processing |
| ESLint | 9 | Code linting |

**Future additions (Phase 2):**
- Electron — wraps the React app into a desktop app (Windows / macOS / Linux)
- Capacitor 8 — wraps the React app into a mobile app (Android)

**Not used (intentionally):**
- No React Router — single card layout, view switching via state
- No Redux / heavy state management — React Context only
- No charting libraries — Radix UI Progress primitives only (keeps bundle small)

---

## 3. Project Structure

```
user_app/
  src/
    views/
      SetupWizard.tsx       ← Page 1 (first run only)
      HomeDashboard.tsx     ← Page 2 (default view)
      Permissions.tsx       ← Page 3
      DeviceInfo.tsx        ← Page 4
    components/
      StatusRing.tsx        ← SECURE / OFFLINE status ring
      GaugeBar.tsx          ← CPU / Memory / Disk progress bars
      TabBar.tsx            ← bottom navigation (Home | Perms | Settings)
      Toggle.tsx            ← permission toggle switch
    context/
      AppContext.tsx         ← global state (auth token, device info, view)
    hooks/
      useProvision.ts       ← calls POST /api/v1/devices/provision
      useTelemetry.ts       ← calls GET /last-telemetry (local IPC)
      useHeartbeat.ts       ← calls POST /api/v1/agent/heartbeat
    App.tsx                 ← view switcher (no router)
    main.tsx                ← app entry point
    index.css               ← Tailwind directives
  index.html
  package.json
  vite.config.ts
  tailwind.config.js
  tsconfig.app.json
```

---

## 4. How to Run Locally

### Prerequisites

| Requirement | Version |
|---|---|
| Node.js | 20.19+ (v20 LTS recommended) |
| npm | 10+ |
| nvm | Any (for Node version switching) |

> **Important:** Node v16 will not work. Vite 8 requires Node 20.19+.

### First time setup

```bash
# 1. Switch to the correct Node version
nvm use 20.19.6

# If nvm is not loaded in your shell, run this first:
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"

# 2. Navigate to the user app directory
cd user_app

# 3. Install dependencies
npm install
```

### Start the dev server

```bash
npm run dev
```

Open **http://localhost:5173/** in your browser.

Press `Ctrl+C` to stop.

### Other commands

```bash
npm run build      # Production build → outputs to dist/
npm run preview    # Serve the production build locally
npm run lint       # Run ESLint checks
```

### Make Node 20 your default (optional)

```bash
nvm alias default 20.19.6
```

This avoids running `nvm use` every time you open a terminal.

---

## 5. Page Working Flow

### Page 1 — Setup / Provisioning Wizard (First Run Only)

**When it shows:** Only on the very first launch, before the device is registered.

**What it does:**
1. User enters their **Site ID** (required) and an optional **Device Name**
2. User clicks **Login with SSO** to authenticate
3. On success, the app calls `POST /api/v1/devices/provision` with the site ID and user identity
4. Backend returns a device token
5. Token is saved securely on the device (localStorage in web / electron-store in Electron)
6. App transitions permanently to Page 2 (Home Dashboard)

**API called:** `POST /api/v1/devices/provision`

```json
{
  "site_id": "site-1234",
  "user_identity": "kasi@company.com",
  "device_name": "Kasi-Laptop"
}
```

---

### Page 2 — Home / Status Dashboard (Default View)

**When it shows:** Every time after provisioning is complete. This is the default landing page.

**What it does:**
- Displays a large **SECURE / ONLINE** (green) or **OFFLINE** (red) status ring
- Shows **Last sync** timestamp
- Shows 3 gauge bars: **CPU**, **Memory**, **Disk** usage percentages
- Shows **Heartbeat** timestamp — last time the agent checked in

**APIs called:**
- `GET /last-telemetry` — local IPC endpoint (Dealdio Python agent on localhost)
  - Returns CPU, Memory, Disk values
- `POST /api/v1/agent/heartbeat` — sent every N seconds to keep the device marked ONLINE
- `GET /api/v1/agent/{device_id}/status` — to determine ONLINE or OFFLINE badge

> **Note:** Until Dealdio's local IPC server is running, the gauge bars will show placeholder/mock data from `mock_telemetry.json`.

---

### Page 3 — Permissions & Access Control

**When it shows:** User taps the "Perms" tab from any page.

**What it does:**
- Shows 4 toggles the employee can turn ON or OFF:
  - Root / Full Access
  - Process Monitoring
  - File System Access
  - Network Monitoring
- Changes apply immediately when a toggle is switched
- Warning label shown to confirm this

**State persistence:** Toggle state is saved and synced to the backend (confirm with client — may also use localStorage as fallback).

---

### Page 4 — Device Info & Settings

**When it shows:** User taps the "Settings" tab from any page.

**What it does:**
- Displays the **Device DNA** table:
  - Hostname
  - MAC Address
  - Local IP
  - OS Details
  - Agent Version
- **Check for Updates** button — checks if a newer agent version is available
- **Disconnect & Unpair** button (red / danger):
  - Wipes the saved auth token from local storage
  - Resets the app back to Page 1 (Setup Wizard)
  - Used when an employee leaves the company or changes device

**API called:** `POST /api/v1/agent/device-dna` (to refresh device DNA info)

---

## 6. Navigation Flow

```
[First Launch]
      │
      ▼
┌─────────────┐     Provisioning complete
│  Page 1     │ ──────────────────────────►  ┌─────────────┐
│  Setup /    │                              │  Page 2     │
│  Wizard     │                              │  Home /     │◄── Default
└─────────────┘                              │  Dashboard  │
                                             └──────┬──────┘
                                                    │  Tab bar
                                        ┌───────────┼───────────┐
                                        ▼                       ▼
                                 ┌────────────┐         ┌────────────┐
                                 │  Page 3    │         │  Page 4    │
                                 │ Permissions│         │Device Info │
                                 └────────────┘         └────────────┘

[Disconnect & Unpair on Page 4] ──────────────────────► Back to Page 1
```

---

## 7. Backend API Reference

All backend endpoints are from PR #151 (`feature/user-app-preparations`).

| Endpoint | Method | Used By | Purpose |
|---|---|---|---|
| `/api/v1/devices/provision` | POST | Page 1 | Register device, get token |
| `/api/v1/agent/heartbeat` | POST | Page 2 | Keep device marked ONLINE |
| `/api/v1/agent/telemetry` | POST | Background | Send CPU/MEM/DISK metrics |
| `/api/v1/agent/{device_id}/status` | GET | Page 2 | Check ONLINE / OFFLINE |
| `/api/v1/agent/device-dna` | POST | Page 4 | Register/update device info |
| `localhost:{PORT}/last-telemetry` | GET | Page 2 | Local IPC — live telemetry |
| `localhost:{PORT}/status` | GET | Page 2 | Local IPC — agent status |
| `localhost:{PORT}/health` | GET | App init | Local IPC — health check |

> **Local IPC port:** Provided by Dealdio. Confirm port number before wiring.

---

## 8. Known Issues & Constraints

| Issue | Status |
|---|---|
| Node v16 not supported — use Node 20.19+ via nvm | Known, documented |
| Gauge bars show mock data until Dealdio IPC is running | Expected, Phase 3 |
| Permission toggle persistence not yet decided (localStorage vs backend) | Pending client confirmation |
| Electron / Capacitor wrapping not yet done | Phase 2 |
| No test setup yet | To be added in Phase 2 |

---

## 9. Phase Roadmap

| Phase | Scope | Status |
|---|---|---|
| Phase 1 | React UI — 4 pages, backend API integration | In progress |
| Phase 2 | Electron (desktop) + Capacitor (Android) wrapping | Upcoming |
| Phase 3 | Wire to Dealdio Python IPC daemon (live telemetry) | Upcoming |
