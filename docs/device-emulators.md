# Device Emulators

Standalone Python scripts that simulate real hardware devices for end-to-end testing of the Dashboard, User App, and device lifecycle flows without physical hardware.

Each emulator runs as an independent process that provisions itself with the backend, then sends heartbeats, telemetry, and responds to commands — just like a real device would.

## Quick start

```bash
# 1. Start the Dashboard (backend + frontend)
./scripts/start-dashboard.sh

# 2. Generate a bootstrap key for your site (via API or operator UI)
#    POST /api/v1/sites/{site_id}/bootstrap-key

# 3. Run the Linux POS emulator
./scripts/start-emulator.sh --site-id site-1 --bootstrap-key <key>

# 4. (Optional) Start the User App to manage the emulated device
./scripts/start-userapp.sh
```

The Dashboard immediately shows the emulated device with its mock DNA, online status, and live telemetry. Commands queued via the Dashboard are picked up, ACKed, and completed with realistic mock results.

## Available emulators

| Emulator | File | OS | Device type |
|----------|------|----|-------------|
| Linux POS | `emulators/linux_pos_emulator.py` | Linux | `pos_terminal` |
| Android POS | — | Android | `pos_terminal` |
| Windows POS | — | Windows | `pos_terminal` |
| macOS POS | — | macOS | `pos_terminal` |
| iOS | — | iOS | `tablet` |
| Web Browser | — | Web | `virtual_terminal` |
| MQTT Sensor | — | Linux | `mobile_scanner` |

Only **Linux POS** is implemented. Each future emulator targets a specific OS and may include OS-specific behaviours (e.g. WNS push on Windows, FCM on Android).

## How an emulator works

```
┌──────────────────┐     POST /devices/bootstrap-provision     ┌──────────────┐
│   Emulator       │ ──────────────────────────────────────────▶              │
│  (standalone     │     POST /agent/device-dna                │   Backend    │
│   Python script) │ ──────────────────────────────────────────▶  (FastAPI)   │
│                  │     POST /agent/heartbeat  (every 10s)    │              │
│  Mock DNA:       │ ──────────────────────────────────────────▶              │
│   MAC, IP,       │     POST /agent/telemetry   (every 15s)   │              │
│   hostname, OS   │ ──────────────────────────────────────────▶              │
│                  │     GET  /devices/pending   (every 15s)   │              │
│  Simulated       │ ◀─────────────────────────────────────────│              │
│   CPU/mem/disk   │     POST /commands/{id}/ack               │              │
│                  │ ──────────────────────────────────────────▶              │
│                  │     PUT  /commands/{id}/status (result)    │              │
│                  │ ──────────────────────────────────────────▶              │
└──────────────────┘                                            └──────────────┘
```

### Lifecycle

1. **Config** — The emulator reads a JSON config file or CLI arguments specifying backend URL, site ID, bootstrap key, mock DNA values, and interval timings.
2. **Provision** — On first run, calls `POST /devices/bootstrap-provision` to register the device. Credentials (`device_id`, `api_key`) are saved to `~/.homepot/emulators/<device_name>.json`.
3. **DNA registration** — Calls `POST /agent/device-dna` with the mock MAC address, local IP, and OS details so the backend has realistic device identity data.
4. **Loops** — Three concurrent async loops run until shutdown:
   - **Heartbeat** — `POST /agent/heartbeat` at a configurable interval
   - **Telemetry** — `POST /agent/telemetry` with simulated CPU/memory/disk metrics, network latency, and runtime uptime (`uptime_seconds`)
   - **Command polling** — `GET /devices/pending`, ACK each command, simulate execution, then report result via `PUT /devices/{command_id}/status`; `status_request` returns a live status snapshot to Live Logs, and composed push commands (`update_pos_payment_config`, `restart_pos_app`, `health_check`, custom) are applied/acknowledged and summarised to Live Logs. Successful pushes are recorded in Push History (`POST /agent/config-history`); a push that fails on the device is recorded there too with `success=false` and the failure reason, and posts an error-level line to Live Logs.
   - **Alert injection** — `POST /agent/alert` with occasional network-latency spikes, so the Dashboard's Alerts tab is populated

### Persistence

Credentials are persisted across restarts. If the emulator is stopped and re-run, it skips provisioning and resumes from its saved credentials. To force re-provisioning, delete the credentials file at `~/.homepot/emulators/<device_name>.json`.

### Restarting

**Standalone** — Press `Ctrl+C` in the terminal where it's running, then re-launch:

```bash
# Stop any running instance
pkill -f linux_pos_emulator.py

# Re-launch
./scripts/start-emulator.sh
```

**User App (Electron)** — Quit and re-open the User App. The Electron main process kills the child emulator on quit; re-opening restarts it automatically when the setup-to-home flow completes.

**Why restart?** The emulator re-registers device DNA on each startup. If backend logic was updated (e.g. new fields like `device_source`), restarting the emulator ensures the device record picks up those changes.

## Configuration reference

### Config file (`emulators/linux_pos_emulator.json`)

| Field | Default | Description |
|-------|---------|-------------|
| `backend_url` | `http://localhost:8000` | Backend API root URL |
| `site_id` | — | Site ID to provision under |
| `bootstrap_key` | — | Bootstrap key for self-enrolment |
| `device_name` | `linux-pos-emulator-1` | Human-readable device name |
| `device_type` | `pos_terminal` | Device type category |
| `os_details` | `Linux 6.8.0 (Debian 12)` | Operating system label |
| `mock_mac` | `02:42:ac:11:00:02` | MAC address reported as device DNA |
| `mock_ip` | `192.168.1.100` | Local IP reported as device DNA |
| `mock_hostname` | `linux-pos-001` | Hostname reported as device DNA |
| `heartbeat_interval_seconds` | `10` | Seconds between heartbeats |
| `telemetry_interval_seconds` | `15` | Seconds between telemetry samples |
| `command_poll_interval_seconds` | `15` | Seconds between pending-command polls |
| `command_failure_rate` | `0.1` | Probability (0..1) a pushed command fails on the device (config update, app restart, custom). Set to `1.0` to force failures for testing. |

### CLI flags

Every config field maps to a `--flag`. CLI values override config file values.

```bash
python emulators/linux_pos_emulator.py \
  --site-id site-1 \
  --bootstrap-key abc123... \
  --device-name "My Custom POS" \
  --mock-mac "aa:bb:cc:dd:ee:ff" \
  --mock-ip "10.0.0.50" \
  --heartbeat-interval 5
```

## Running a full simulation session

```
Terminal 1:  ./scripts/start-dashboard.sh
             # Backend on :8000, Dashboard on :5173

Terminal 2:  ./scripts/start-emulator.sh --site-id site-1 --bootstrap-key <key>
             # Emulator provisions, heartbeats, sends telemetry

Terminal 3:  ./scripts/start-userapp.sh
             # User App on :5174 — login and manage the emulated device
```

The Dashboard at http://localhost:5173 shows the emulated device in the device list with:
- Mock hostname, MAC, IP (from DNA registration)
- `online` connectivity (via heartbeats)
- Live CPU/memory/disk gauges (via telemetry)
- Command queueing and history

Queuing a command via the Dashboard (e.g. `restart`, `ping`, `update_config`) sends it to the emulator which ACKs, simulates execution, and reports a result. The full round-trip takes a few seconds.

## Command response simulation

| Command type | Simulated result |
|-------------|------------------|
| `restart` | `reboot_time_seconds: 45` |
| `shutdown` | Immediate completion |
| `update_config` | `applied_settings: { log_level: "INFO" }` |
| `ping` | Random latency 5–50 ms |
| *(unknown)* | No-op with warning |

### Push-command failure simulation

Composed push commands (`update_pos_payment_config`, `restart_pos_app`, `health_check`, custom) have a configurable failure probability controlled by `--command-failure-rate` (default `0.1`). When a push fails the emulator:

- reports `status: "failed"` to `PUT /devices/{command_id}/status`, so the device command is marked `failed` with the reason in its `result`;
- posts an **error-level** line to Live Logs (e.g. `Command received: Apply Config (update_pos_payment_config) | Configuration download failed: Connection timeout`);
- records a **failed** entry in Push History with the reason in the card title and `result` details (rendered with a red X on the Push History page).

`health_check` fails when any of its tests fails (e.g. `network=fail: timeout`). Set `--command-failure-rate 1.0` to make every pushed config/restart/custom command fail, which makes the failure path easy to demo end-to-end.

## Creating a new emulator

Each emulator is a standalone runnable script. The simplest approach is to copy `linux_pos_emulator.py` and adjust:

1. **Config defaults** — Change the OS details, device type, mock MAC/IP/hostname defaults.
2. **Simulated metrics** — Override `SimulatedMetrics` for OS-specific metrics (e.g. Android battery level, iOS thermal state).
3. **Command responses** — Add OS-specific command handlers in `_simulate_command_result`.
4. **Platform-specific behaviours** — Override loops or add new ones (e.g. WNS channel registration for Windows, FCM token refresh for Android).
5. **Config file** — Create a dedicated JSON config with appropriate defaults.

### Directory layout

```
emulators/
├── __init__.py
├── linux_pos_emulator.py       # Linux POS (implemented)
├── linux_pos_emulator.json      # Linux POS config example
├── android_pos_emulator.py      # Android POS (future)
├── android_pos_emulator.json    # Android POS config example
├── windows_pos_emulator.py      # Windows POS (future)
└── ...
```

## Credential storage

Credentials live at `~/.homepot/emulators/<device_name>.json` with `0600` permissions:

```json
{
  "device_id": "a1b2c3d4-...",
  "api_key": "mM2...",
  "site_id": "site-1",
  "device_name": "linux-pos-emulator-1",
  ...
}
```

Emulators can run multiple instances simultaneously by using different `device_name` values (each gets its own credentials file and provisions independently).

## User App integration (design sketch)

The emulator can be spawned and managed directly from the User App's Electron shell, giving developers the full "real device" experience — the setup wizard provisions a device, the emulator starts as a background process, and the User App shows/manages it just like a physical device.

### Architecture

```
User App (Electron)
  ┌──────────────────────────────┐
  │ Renderer (React)            │
  │  - SetupWizard adds emulator │
  │    mode toggle + type picker │
  │  - Existing views unchanged  │
  └──────────┬───────────────────┘
             │ IPC
  ┌──────────▼───────────────────┐
  │ Main Process (Node)         │
  │  - emulator:start handler   │
  │  - emulator:stop handler    │
  │  - emulator:status handler  │
  │  - spawns/kills child proc  │
  │  - watches credential file  │
  └──────────┬───────────────────┘
             │ child_process.spawn
  ┌──────────▼───────────────────┐
  │ Emulator (Python)           │
  │  - Provisions via backend   │
  │  - Writes credentials to    │
  │    ~/.homepot/emulators/    │
  │  - Runs loops until killed  │
  └──────────────────────────────┘
```

### New IPC handlers (Electron main)

| Channel | Direction | Purpose |
|---------|-----------|---------|
| `emulator:start` | Renderer → Main | Spawn emulator with config, returns `{device_id, api_key}` when provisioned |
| `emulator:stop` | Renderer → Main | Kill the emulator child process |
| `emulator:status` | Renderer → Main | Return `{running: bool, pid, device_id}` |

### SetupWizard flow change

1. **Step 1** (existing): Site ID, hostname, device type, OS
2. **Step 2** (new): Mode selection — "Real device" (current flow) or **"Launch emulator"**
3. **Step 3** (new, emulator mode only): Emulator type picker — Linux POS, Android POS (future), etc.
4. **Review** (modified): Shows config + "Start Emulator" button; on click, Electron writes a temp JSON config, spawns the Python emulator, waits for it to provision and write credentials, then navigates to `/home`

### Lifecycle

- **Startup**: Electron spawns `python3 emulators/linux_pos_emulator.py --config <temp-file>`. The temp config contains backend URL, site ID, bootstrap key, and mock DNA values for the selected emulator type.
- **Provisioning wait**: Main process polls `~/.homepot/emulators/<device_name>.json` until it appears (emulator writes it after provisioning).
- **Runtime**: Main process monitors the child process — if it dies unexpectedly, a warning banner appears in the UI.
- **Shutdown**: On app quit or unpair, main process sends SIGTERM → waits 3 s → SIGKILL if needed.
- **Restart**: If the User App reopens and credentials still exist, the device is shown as provisioned (no emulator restart needed if already running).

### Design decisions

| Decision | Chosen approach |
|----------|-----------------|
| **Dev-only vs toggleable** | Dev-only (`import.meta.env.DEV`). Hidden from production builds — it is a developer tool, not a user feature. |
| **Python discovery** | Try `.venv/bin/python3` first, then fall back to `python3` on PATH, with a configurable override. |
| **Single vs multiple** | Single emulator per User App instance. Matches the real-world model (one device per User App). |
| **Emulator output** | Stdout/stderr piped to `~/.homepot/emulators/<name>.log`. A debug panel in Electron DevTools can tail it. |

### Preload API shape

```typescript
interface Window {
  electronAPI?: {
    // Existing channels
    credentials: { ... }
    device: { ... }
    app: { ... }

    // New channels
    emulator: {
      start(config: EmulatorStartConfig): Promise<{ deviceId: string; apiKey: string }>
      stop(): Promise<boolean>
      status(): Promise<{ running: boolean; pid?: number; deviceId?: string }>
    }
  }
}

interface EmulatorStartConfig {
  emulatorType: 'linux_pos' | 'android_pos'  // | ...future
  backendUrl: string
  siteId: string
  bootstrapKey: string
  deviceName: string
  mockMac?: string
  mockIp?: string
  mockHostname?: string
  heartbeatInterval?: number
  telemetryInterval?: number
}
```

### SetupWizard emulator step mock-up

```
┌─────────────────────────────────────────┐
│  HOMEPOT Agent          Step 2 of 4     │
│                                         │
│  ● ● ○ ○                                │
│                                         │
│  How would you like to set up?          │
│                                         │
│  ┌─────────────────────────────────────┐│
│  │  ◉  Launch emulated device          ││
│  │     (for development / testing)     ││
│  │                                     ││
│  │  ○  Set up a real device            ││
│  └─────────────────────────────────────┘│
│                                         │
│  ┌─────────────────────────────────────┐│
│  │ Device type:  [Linux POS       ▼]  ││
│  │ OS:           [Linux 6.8      ▼]  ││
│  │ Mock MAC:     02:42:ac:11:00:02    ││
│  │ Mock IP:      192.168.1.100        ││
│  └─────────────────────────────────────┘│
│                                         │
│         [  Next → ]                     │
└─────────────────────────────────────────┘
```

### Implementation order

1. Add `emulator:start`, `emulator:stop`, `emulator:status` IPC handlers to `electron/main.ts`
2. Expose emulator channels in `electron/preload.ts`
3. Update `SetupWizard.tsx` — add mode selection step and emulator type picker
4. Add `EmulatorStartConfig` type to `credentialStorage.ts` or a new types file
5. Update `AppContext.tsx` — add emulator state (`isEmulatorRunning`, `emulatorType`)
6. Wire ReviewStep to call `window.electronAPI.emulator.start()` instead of the dev-mode mock path

## Related documentation

- [Device lifecycle and ownership](device-lifecycle-and-ownership.md) — Full device lifecycle, PR history, and remaining work
- [Real device agent](real-device-agent.md) — Production agent runtime for physical hardware
- [Agent simulation](agent-simulation.md) — Legacy simulator fleet (23 simulated agents)
- [User App guide](user-app-frontend-guide.md) — Electron-based device management UI
