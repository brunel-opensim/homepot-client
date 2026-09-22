# Windows Device Management

## Overview

HOMEPOT manages Windows devices through a **push-based architecture** with WNS (Windows Notification Service) as the primary wake-up mechanism, falling back to HTTP polling when push is unavailable. Windows devices receive all capabilities including `root_access`, enabling privileged operations through a scoped elevation layer.

**Key architectural principle:** Windows combines push notifications for low-latency command delivery with a robust polling fallback for reliability.

---

## Architecture

### Push Channel (WNS)

The `derive_push_channel()` function in `backend/src/homepot/app/schemas/os_capabilities.py` returns `wns` for Windows:

| Platform | Push Channel | Protocol |
|----------|-------------|----------|
| Android | `fcm` | Firebase Cloud Messaging |
| **Windows** | **`wns`** | **Windows Notification Service** |
| iOS | `apns` | Apple Push Notification service |
| macOS | `None` | HTTP Polling |
| Linux | `None` | HTTP Polling |
| IoT/MQTT | `mqtt` | MQTT Protocol |

### Command Flow Diagram

```
┌──────────────────────────────┐                              ┌─────────────────────────┐
│         BACKEND              │                              │    WINDOWS DEVICE       │
│                              │         WNS Push             │                         │
│  POST /devices/{id}/commands │ ───────────────────────────► │  Agent Runtime          │
│  (queue command)             │                              │  - heartbeat_loop()     │
│         │                    │                              │  - telemetry_loop()     │
│         ▼                    │                              │  - pending_commands_    │
│  DeviceCommand (PENDING)     │ ◄──── GET /devices/pending ─ │    loop()               │
│         │                    │                              │                         │
│         │                    │ ◄──── POST .../ack ──────── │  ACK command            │
│  DeviceCommand (SENT)        │                              │                         │
│         │                    │                              │  Execute command        │
│         │                    │ ◄──── PUT .../status ────── │  Report result          │
│  DeviceCommand (COMPLETED)   │                              │                         │
│                              │                              │  IPC server (localhost) │
│  push_channel: wns           │                              │  (real device app)      │
│  push_token: wns://...       │                              │                         │
│                              │                              │  OS Elevation Layer     │
│  WNS push notification sent  │                              │  (homepot-ctl.ps1 +     │
│  for immediate wake-up       │                              │   scheduled task)       │
│                              │                              │                         │
│  Fallback: HTTP polling      │                              │  Fallback: 60s polling  │
│  when WNS unavailable        │                              │  when push unavailable  │
└──────────────────────────────┘                              └─────────────────────────┘
```

---

## Key Files

| File | Role |
|------|------|
| `backend/src/homepot/app/schemas/os_capabilities.py` | OS classification, capabilities, push channel derivation |
| `backend/src/homepot/agent/real_device_agent.py` | Real agent runtime — heartbeat, telemetry, command polling loops |
| `backend/src/homepot/agent/utils/command_poller.py` | Command polling, permission gating, elevation-aware execution |
| `backend/src/homepot/agent/utils/elevation.py` | Scoped elevation via `homepot-ctl.ps1` helper (Windows scheduled task) |
| `backend/src/homepot/agent/credential_storage.py` | Platform-aware storage — Windows uses Credential Manager or file |
| `backend/src/homepot/push_notifications/wns_windows.py` | WNS push provider for Windows devices |
| `user_app/electron/main.ts` | Electron main — Windows UAC elevation install |
| `user_app/electron/privileged/homepot-ctl.ps1` | Windows elevation helper script |
| `user_app/electron/privileged/homepot-ctl-install.ps1` | Windows one-time installer with UAC |
| `user_app/src/views/Permissions.tsx` | Monitor/Manage toggles — Windows enablement |

---

## OS Capabilities

Windows receives **all capabilities enabled** (`os_capabilities.py:60-89`):

```python
{
    "root_access": True,
    "command_execution": True,
    "process_monitoring": True,
    "filesystem_access": True,
    "network_monitoring": True,
}
```

This means Windows devices can execute privileged operations (restart, shutdown, script execution) through the scoped elevation layer.

---

## Command Polling Details

### Agent-Side Loops

The real device agent (`real_device_agent.py`) runs several concurrent loops:

1. **`pending_commands_loop()`** (line 333-476): Polls `GET /api/v1/devices/pending` at `command_poll_interval_seconds` (default 60s)
   - Fetches current device permissions from backend
   - Syncs OS elevation state
   - Checks permission gate before ACK
   - ACKs the command via `POST /api/v1/devices/{device_id}/commands/{command_id}/ack`
   - Routes to IPC (for the real device app to execute) or processes locally

2. **`command_result_loop()`** (line 479-521): Picks up results from IPC and reports them back via `PUT /api/v1/devices/{command_id}/status`

3. **`heartbeat_loop()`** (line 674-721): Sends heartbeats to `POST /api/v1/agent/heartbeat`

4. **`telemetry_loop()`** (line 724-778): Sends telemetry to `POST /api/v1/agent/telemetry`

### Server-Side Wake-Up

When a command is queued (`DeviceCommandsEndpoint.py:152-155`):

```python
await send_command_wakeup(device)
```

The `send_command_wakeup()` function (`wakeup.py:71-128`) checks `device.push_channel` and `device.push_token`. For Windows: `push_channel` is `wns`, so a WNS push notification is sent for immediate wake-up.

---

## Windows-Specific Features

### OS Elevation Layer

Windows uses a scoped elevation mechanism via the `homepot-ctl.ps1` helper script and a Windows scheduled task (`elevation.py`):

- **Installation:** Uses PowerShell with UAC elevation (`Start-Process -Verb RunAs`)
- **Execution:** Scheduled task runs with SYSTEM privileges for elevated operations
- **Scope:** Creates an allowlist for `restart`, `shutdown`, `exec` operations
- **Security:** Autonomous teardown when `root_access` is revoked
- **Usage:** Free-form commands (`run_command`, `run_script`) require `root_access` permission and execute through this helper

#### Elevation Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WINDOWS ELEVATION LAYER                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User App (Electron)                                                        │
│  ├─ installManagedElevation()                                               │
│  │   └─ Start-Process -Verb RunAs (UAC prompt)                             │
│  │       └─ homepot-ctl-install.ps1                                        │
│  │           ├─ Copy homepot-ctl.ps1 to %PROGRAMDATA%\Homepot\             │
│  │           ├─ Create allowlist.json                                       │
│  │           └─ Register scheduled task (HOMEPOT-Elevation)                 │
│  │                                                                       │
│  └─ deprovisionManagedElevation()                                           │
│      └─ Unregister-ScheduledTask + remove files                            │
│                                                                             │
│  Agent (Python)                                                             │
│  ├─ elevation.elevated_command_argv("restart")                             │
│  │   └─ ["powershell", "-File", "homepot-ctl.ps1", "run", "restart"]       │
│  │                                                                       │
│  ├─ elevation.elevated_exec_argv()                                         │
│  │   └─ ["powershell", "-File", "homepot-ctl.ps1", "run", "exec"]          │
│  │       └─ Script text read from stdin                                    │
│  │                                                                       │
│  └─ Scheduled Task (HOMEPOT-Elevation)                                     │
│      └─ Runs as SYSTEM with highest privileges                             │
│          └─ Executes homepot-ctl.ps1 run <operation>                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Elevation Helpers

| File | Role |
|------|------|
| `homepot-ctl.ps1` | Windows elevation helper — executes privileged operations |
| `homepot-ctl-install.ps1` | One-time installer — copies helper and registers scheduled task |

#### Elevation Status

The elevation layer reports status via:

```python
elevation.elevation_status()  # Returns dict with supported, installed, provisioned, ops
```

On Windows:
- `supported`: True (platform is Windows)
- `installed`: True if `homepot-ctl.ps1` exists at `%PROGRAMDATA%\Homepot\`
- `provisioned`: True if scheduled task `HOMEPOT-Elevation` exists or marker file exists
- `ops`: `["restart", "shutdown", "exec"]`

### Credential Storage

On Windows (`sys.platform == "win32"`), the credential storage factory (`credential_storage.py`) tries:

1. **`WindowsCredentialManagerStorage`** — Uses Windows Credential Manager via the `keyring` library
2. **`WindowsFileStorage`** — Falls back to `%APPDATA%\Homepot\credentials` with restricted ACLs

### WNS Push Notifications

Windows receives push notifications via WNS (`wns_windows.py:1-829`):

- **Registration:** Device receives a WNS push token during enrollment
- **Delivery:** Backend sends WNS push for immediate command wake-up
- **Fallback:** Falls back to HTTP polling if WNS is unavailable
- **Configuration:** Requires Azure `package_sid` and `secret_key` for WNS authentication

### Windows-Specific Command Appliers

The command poller (`command_poller.py`) includes Windows-specific implementations:

| Command | Implementation |
|---------|---------------|
| `brightness` | Uses PowerShell `Get-WmiObject` + `WmiMonitorBrightnessMethods` |
| `volume` | Uses PowerShell `New-Object -ComObject WScript.Shell` |

### Device Recovery (Start at Login)

Packaged builds of the User App register a **Windows startup entry**:

- Auto-enabled on first launch
- Starts hidden in the system tray
- Source/dev checkouts are exempt (only when `app.isPackaged` is true)
- Operator control via Device Info → Launch Settings → Start at login

---

## Security Considerations

### Device Authentication

- Each device gets a unique `device_id` and `api_key` (generated via `secrets.token_urlsafe(32)`)
- API key is hashed (`hash_password()`) and stored in `devices.api_key_hash`
- Agent sends credentials via headers: `X-Device-ID` and `X-API-Key`
- Enrolment uses a one-time `claim_token` with intent-based flow

### Command Security

- **Permission gate:** Every command type maps to required device permissions
- **Lifecycle check:** Only devices in `ACTIVE` state accept commands
- **Access control:** Operator-level site access required to queue commands
- **Audit logging:** All command lifecycle transitions are audit-logged
- **Privileged commands:** `run_command` and `run_script` require `root_access` permission

### Elevation Security

- **Scoped elevation:** Only `restart`, `shutdown`, and `exec` operations are allowlisted
- **Scheduled task:** Runs with SYSTEM privileges but only for the elevation helper
- **Autonomous teardown:** Removing `root_access` permission automatically removes the scheduled task
- **No blanket sudo:** Windows elevation is scoped to the helper, not a general admin context

### Credential Security

- Windows uses Credential Manager (via `keyring` library) or file with restricted ACLs
- Per-run IPC bearer token (random `secrets.token_urlsafe(32)`) for localhost IPC endpoints

---

## Comparison with Other Platforms

| Aspect | Windows (Push+Polling) | macOS (Polling) | iOS/Android (Push) |
|--------|----------------------|-----------------|-------------------|
| **Command delivery** | WNS push + 60s polling fallback | HTTP polling only | Push notification only |
| **Latency** | Near-instant (< 5s) with WNS | Up to 60 seconds | Near-instant (< 5s) |
| **Push channel** | WNS | None | FCM/APNs |
| **Elevation method** | Scheduled task (SYSTEM) | sudo + sudoers | N/A (sandboxed) |
| **Credential storage** | Credential Manager / file | Keychain / file | Keychain / Keystore |
| **Battery impact** | Low (push-driven) | Moderate (periodic polling) | Low (push-driven) |
| **Offline behavior** | Commands queue until push delivery | Commands queue until next poll | Commands queue until push delivery |

---

## Testing

### Windows POS Emulator

A Windows POS emulator is available for testing (`emulators/windows_pos_emulator.py`):

```bash
./scripts/start-emulator.sh --site-id site-it-demo1 --bootstrap-key <key> --device-name demo-windows-pos-1
```

The emulator:
- Uses `os_details: "Windows 11"` and `device_type: "pos_terminal"`
- Gets full permission capability map including `root_access`
- Runs as a thin wrapper around the shared `pos_engine.py`

### Manual Testing

To test command execution on a real Windows device:

1. Register the device via the Dashboard or API
2. Grant Monitor and Manage permissions in the User App
3. Verify the elevation helper is installed (`homepot-ctl.ps1` exists)
4. Queue a command: `POST /api/v1/devices/{device_id}/commands`
5. Wait for the push notification or next polling interval
6. Verify the command is ACKed and executed
7. Check the result is reported back

### Elevation Testing

To test the Windows elevation layer:

1. **Install test:** Grant Manage → verify UAC prompt → verify scheduled task created
2. **Execute test:** Queue `restart` command → verify it runs via elevated helper
3. **Deprovision test:** Revoke Manage → verify scheduled task removed
4. **Fallback test:** Test without elevation helper → verify actionable error messages

---

## Summary

Windows device management in HOMEPOT uses a hybrid push+polling architecture:

- **WNS push channel** — Near-instant command delivery with polling fallback
- **Full capability set** — All permissions including `root_access` enabled
- **Scoped elevation** — Scheduled task runs helper with SYSTEM privileges
- **Platform-native tooling** — PowerShell for elevation, WNS for push notifications
- **Secure elevation** — Autonomous teardown when consent is revoked
- **No third-party push SDK** — Uses Microsoft's WNS for push delivery

This architecture combines low latency (WNS push) with reliability (polling fallback) and secure, scoped elevation for privileged operations.
