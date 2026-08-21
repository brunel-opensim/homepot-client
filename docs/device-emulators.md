# Device Emulators

Standalone Python scripts that simulate real hardware devices for end-to-end testing of the Dashboard, User App, and device lifecycle flows without physical hardware.

Each emulator runs as an independent process that provisions itself with the backend, then sends heartbeats, telemetry, and responds to commands — just like a real device would.

!!! warning "Disable the in-process agent simulator before emulating"
    The backend's in-process agent simulator (`ENABLE_AGENT_SIMULATION=true`, the
    default in `backend/.env`) starts a simulated agent for **every** active
    POS/IoT device on startup. If it is left on while an emulator runs, it writes
    additional fake telemetry into the emulated device — and into any `real`
    device — which corrupts the `real`/`controlled`/`simulated` provenance that
    the KPI export relies on.

    Before starting an emulator, set `ENABLE_AGENT_SIMULATION=false` in
    `backend/.env` (or the environment) and restart the backend. See
    [Getting started — Simulation](getting-started.md) for what the simulator
    does when enabled.

## Quick start

```bash
# 1. Start the Dashboard (backend + frontend)
./scripts/start-dashboard.sh

# 2. Generate a bootstrap key for your site (via API or operator UI)
#    POST /api/v1/sites/{site_id}/bootstrap-key

# 3. Run the Linux POS emulator
./scripts/start-emulator.sh --site-id site-it-demo1 --bootstrap-key <key> --device-name demo-pos-1
#    Use a different --device-name per emulator to run several on one site

# 4. (Optional) Start the User App to manage the emulated device
./scripts/start-userapp.sh
```

The Dashboard immediately shows the emulated device with its mock DNA, online status, and live telemetry. Commands queued via the Dashboard are picked up, ACKed, and completed with realistic mock results.

## Available emulators

| Emulator | File | OS | Device type |
|----------|------|----|-------------|
| Linux POS | `emulators/linux_pos_emulator.py` | Linux | `pos_terminal` |
| Android POS | `emulators/android_pos_emulator.py` | Android | `pos_terminal` |
| Windows POS | `emulators/windows_pos_emulator.py` | Windows | `pos_terminal` |
| macOS POS | `emulators/macos_pos_emulator.py` | macOS | `pos_terminal` |
| iOS | `emulators/ios_pos_emulator.py` | iOS | `tablet` |
| Web Browser | — | Web | `virtual_terminal` |
| MQTT Sensor | — | Linux | `mobile_scanner` |

**Linux POS**, **Android POS**, **Windows POS**, **macOS POS** and **iOS** are implemented. They are thin wrappers around the shared engine in `emulators/pos_engine.py`. Each OS only overrides identity defaults (e.g. Android: `Android 16`, mock MAC `02:42:ac:11:00:03`; Windows: `Windows 11`; iOS uses device type `tablet`); each one's OS capability map is derived from the OS string (Linux/macOS keep root access; Android/Windows/iOS do not; iOS is further restricted to network monitoring only). Each future emulator targets a specific OS and may include OS-specific behaviours (e.g. WNS push on Windows, FCM on Android).

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

`start-emulator.sh` runs the emulator in the background. Each instance writes
to its own per-instance log/PID file, named after the `--device-name` (or the
emulator type when no name is given):
`logs/emulator-<instance>.log` and `logs/emulator-<instance>.pid`. This means
several emulators can run at once — just give each a unique `--device-name`.

```bash
# Launch an emulator (each instance gets its own log/PID file)
./scripts/start-emulator.sh --emulator android --device-name demo-android-1

# Launch another emulator concurrently with a different name
./scripts/start-emulator.sh --emulator macos --device-name demo-macos-1

# Watch a specific instance's live output
tail -f logs/emulator-demo-macos-1.log

# Stop one instance by name (its --device-name, else emulator type)
./scripts/stop-emulator.sh demo-macos-1

# Stop ALL emulators
./scripts/stop-emulator.sh
```

`start-emulator.sh` accepts an `--emulator linux|android|windows|macos|ios`
flag (default `linux`) that selects the emulator script and its default config.
Any emulator launch arguments — `--backend-url`, `--site-id`, `--bootstrap-key`,
`--device-name`, `--os-details`, `--permission-consent-mode`, … — are forwarded
to the Python emulator. A repeat launch of the **same** instance (same name) is
refused while it is running; different instances run side by side.

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
| `permission_consent_mode` | `auto` | How the device owner consents to permissions. `auto` grants supported permissions at boot then toggles them over time (and mostly consents to operator requests); `fixed` grants all supported at boot and keeps them; `deny` refuses everything. |
| `permission_sync_interval_seconds` | `20` | Seconds between device-initiated permission-consent syncs. |

### CLI flags

Every config field maps to a `--flag`. CLI values override config file values.

```bash
python emulators/linux_pos_emulator.py \
  --site-id site-it-demo1 \
  --bootstrap-key abc123... \
  --device-name "My Custom POS" \
  --mock-mac "aa:bb:cc:dd:ee:ff" \
  --mock-ip "10.0.0.50" \
  --heartbeat-interval 5 \
  --permission-consent-mode auto
```

## Running a full simulation session

```
Terminal 1:  ./scripts/start-dashboard.sh
             # Backend on :8000, Dashboard on :5173

Terminal 2:  ./scripts/start-emulator.sh --site-id site-it-demo1 --bootstrap-key <key> --device-name demo-pos-1
             # Emulator provisions, heartbeats, sends telemetry
             # Use a different --device-name per emulator to run several on one site
             # Live output: tail -f logs/emulator-demo-pos-1.log

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

### Permission simulation

The emulator models the **device-side consent** half of the platform permission
model (see `backend/src/homepot/app/schemas/permissions.py`). The four
permission keys are `root_access`, `command_execution`, `process_monitoring`,
`filesystem_access`, `network_monitoring`; which keys a device can support are derived from its
`os_details` (mirrored from the backend's `derive_capabilities`), so changing
the emulated OS changes the capabilities the Dashboard shows.

On the emulator:

- On boot it derives its capabilities from `os_details`, applies a default
  consent based on `--permission-consent-mode`, and syncs it via
  `PATCH /devices/device/{id}/permissions`.
- **Device-initiated consent** (`auto`) — a loop periodically toggles the granted
  set (grant/revoke) to mimic a device owner changing their mind, so the
  Dashboard's capabilities/permissions matrix updates over time.
- **Operator-initiated request** — an operator pushes the
  `request_permission` command with a payload such as
  `{"permission": "process_monitoring", "action": "grant", "requested_by": "Alice"}`.
  The emulator simulates a consent prompt: in `auto` mode it mostly consents
  (occasionally denies), and `deny` mode refuses. On a decision it PATCHes
  the new permission, posts an `info`/`error` line to Live Logs, and emits a
  `permission_change` Audit Trail event.

`--permission-consent-mode` values:

| Mode | Boot consent | Consent loop | Operator `request_permission` |
|------|--------------|--------------|-------------------------------|
| `auto` | grant all supported | toggles grants over time | mostly consents (~80%), occasionally denies |
| `fixed` | grant all supported | none (static) | always consents |
| `deny` | grant nothing | none | always denies |

Example:
```bash
./scripts/start-emulator.sh --site-id site-it-demo1 --bootstrap-key <key> --device-name demo-pos-1 --permission-consent-mode deny
```

## OS-specific behaviour: push channels

> **See also:** the terminology for `bootstrap_key`, `api_key`, `device_token`
> and `push_channel` is defined in
> [`docs/device-credentials-and-tokens.md`](device-credentials-and-tokens.md).

The engine models how each OS receives commands. Desktop / POS runtimes
(Linux, macOS) use plain HTTP polling (`/devices/pending`), while push-capable
OSes also derive a **push channel** and a synthetic registration token, mirroring
how the real agent registers a `device_token` with the backend:

| OS | Push channel | Token shape |
|----|--------------|-------------|
| Android | `fcm` | `fcm:emulator:<hex>` |
| Windows | `wns` | `https://wns.notify.windows.com/?token=emulator:<hex>` |
| iOS / iPadOS | `apns` | `apns://emulator:<hex>` |
| Linux, macOS | `None` | polling only (no token) |

This is derived by `derive_push_channel(os_details)` in `pos_engine.py`; nothing
extra is needed in a thin wrapper — setting `os_details` to a push-capable OS
selects the channel automatically. Test it with:

```python
from pos_engine import derive_push_channel
assert derive_push_channel("Android 14") == "fcm"
assert derive_push_channel("Linux 6.8.0 (Debian 12)") is None
```

On boot, a push-capable emulator prints its channel + token and includes
`device_token` in the `device-dna` registration payload. `push_channel` and
`push_token` also appear in every status report. When a command is received the
engine logs an OS-specific delivery note (e.g. `restart_pos_app pushed via WNS`).

These are the engine's **OS behavior hooks**:

- `POSEmulator.push_channel` — the push transport (`None` for polling-only).
- `POSEmulator.push_token` — the synthetic registration token.
- `POSEmulator._push_delivery_note(command_type)` — human-readable delivery note.
- `derive_push_channel(os_details)` — free function mirroring the backend mapping.

To add a new push transport (e.g. an alternative), extend `derive_push_channel`,
the `prefix` map in `_new_push_token`, and the `channel` map in
`_push_delivery_note`; no changes are needed in the OS wrappers.

## Creating a new emulator

Each emulator is a standalone runnable script. The quickest way to add a new OS is to create a thin wrapper that imports the shared engine from `pos_engine.py` and overrides the identity defaults, exactly like `android_pos_emulator.py`:

```python
from pos_engine import POSEmulator, main

WINDOWS_DEFAULTS = {
    "device_name": "windows-pos-emulator-1",
    "os_details": "Windows 11",
    "mock_mac": "02:42:ac:11:00:04",
    "mock_hostname": "windows-pos-001",
}

def windows_main(argv=None):
    main(argv, defaults=WINDOWS_DEFAULTS, emulator_class=POSEmulator, banner="HOMEPOT Windows POS Emulator")
```

For OS-specific behaviour beyond identity, add it to the shared engine (`pos_engine.py`) in an OS-conditional way, or subclass `POSEmulator`:

1. **Config defaults** — Change the OS details, device type, mock MAC/IP/hostname defaults.
2. **Simulated metrics** — Override `SimulatedMetrics` for OS-specific metrics (e.g. Android battery level, iOS thermal state).
3. **Command responses** — Add OS-specific command handlers in `_simulate_command_result`(keyed on `os_details`).
4. **Platform-specific behaviours** — Override loops or add new ones (e.g. WNS channel registration for Windows, FCM token refresh for Android).
5. **Config file** — Create a dedicated JSON config with appropriate defaults.

### Directory layout

```
emulators/
├── __init__.py
├── pos_engine.py                # Shared emulator engine (all behaviour)
├── linux_pos_emulator.py        # Linux POS (thin wrapper)
├── linux_pos_emulator.json      # Linux POS config example
├── android_pos_emulator.py      # Android POS (thin wrapper)
├── android_pos_emulator.json    # Android POS config example
├── windows_pos_emulator.py      # Windows POS (thin wrapper)
├── windows_pos_emulator.json    # Windows POS config example
├── macos_pos_emulator.py        # macOS POS (thin wrapper)
├── macos_pos_emulator.json      # macOS POS config example
├── ios_pos_emulator.py          # iOS (thin wrapper; device type "tablet")
├── ios_pos_emulator.json        # iOS config example
└── ...
```

## Credential storage

Credentials live at `~/.homepot/emulators/<device_name>.json` with `0600` permissions:

```json
{
  "device_id": "a1b2c3d4-...",
  "api_key": "mM2...",
  "site_id": "site-it-demo1",
  "device_name": "linux-pos-emulator-1",
  ...
}
```

Emulators can run multiple instances simultaneously by using different `device_name` values (each gets its own credentials file and provisions independently).

## User App integration

The emulator can be spawned and managed directly from the User App's Electron shell, giving developers the full "real device" experience — the setup wizard provisions a device, the emulator starts as a background process, and the User App shows/manages it just like a physical device.

This integration is implemented for all five emulators (Linux, Android,
Windows, macOS, iOS). The OS type picker in the setup wizard lists every
supported emulator with its identity (OS details, device type); to launch a
different OS, just select it there. The Electron main process resolves the
chosen ``emulator_type`` against a per-OS profile
(``EMULATOR_PROFILES`` in ``user_app/electron/main.ts``) for ``os_details``,
``device_type`` and ``mock_mac`` instead of branching on Android-vs-Linux, so
every wrapper is selectable. On resume, the saved ``emulator_type`` is used, or
inferred from ``os_details`` when absent.

Run the Electron workflow with `cd user_app && npm run electron:dev`; the
browser-only server at `http://localhost:5174` can perform the setup handshake
but cannot spawn an emulator process.

Before mode selection, Setup Step 1 performs the pre-enrolment handshake:

1. Site ID entry prompts for the administrator-provided bootstrap key.
2. The Site ID/key pair is verified together through
  `POST /devices/verify-bootstrap`; invalid pairs receive one generic result.
3. Device-name availability is checked within the verified site through
  `POST /devices/check-name`.
4. **Next** is enabled only after site credentials are verified, the device
  name is available, and the local required fields are complete.

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

### IPC handlers (Electron main)

| Channel | Direction | Purpose |
|---------|-----------|---------|
| `emulator:start` | Renderer → Main | Spawn emulator with config, returns `{device_id, api_key}` when provisioned |
| `emulator:stop` | Renderer → Main | Kill the emulator child process |
| `emulator:status` | Renderer → Main | Return `{running: bool, pid, device_id}` |

### SetupWizard flow

1. **Step 1** (existing): Site ID, hostname, device type, OS
2. **Step 2** (new): Mode selection — "Real device" (current flow) or **"Launch emulator"**
3. **Step 3** (new, emulator mode only): Emulator type picker — Linux POS, Android POS (future), etc.
4. **Review** (modified): Shows config + "Start Emulator" button; on click, Electron writes a temp JSON config, spawns the Python emulator, waits for it to provision and write credentials, then navigates to `/home`

### Lifecycle

- **Startup**: Electron spawns `python3 emulators/<os>_pos_emulator.py --config <temp-file>` (e.g. `linux_pos_emulator.py` or `android_pos_emulator.py`). The temp config contains backend URL, site ID, bootstrap key, and mock DNA values for the selected emulator type.
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

### Implementation status

1. `emulator:start`, `emulator:stop`, and `emulator:status` IPC handlers are implemented in `electron/main.ts`.
2. Emulator channels are exposed through `electron/preload.ts`.
3. `SetupWizard.tsx` includes mode selection and Linux/Android emulator type selection.
4. `AppContext.tsx` tracks emulator mode, type, and runtime state.
5. Review completion calls `window.electronAPI.emulator.start()` in Electron emulator mode.

## Related documentation

- [Device lifecycle and ownership](device-lifecycle-and-ownership.md) — Full device lifecycle, PR history, and remaining work
- [Real device agent](real-device-agent.md) — Production agent runtime for physical hardware
- [Agent simulation](agent-simulation.md) — Legacy simulator fleet (23 simulated agents)
- [User App guide](user-app-frontend-guide.md) — Electron-based device management UI
