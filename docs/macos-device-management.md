# macOS Device Management

## Overview

HOMEPOT manages macOS devices through a **polling-based architecture**. Unlike iOS/Android/Windows devices that receive push notifications to wake up, macOS devices rely entirely on HTTP polling for command delivery. This is a deliberate design choice — macOS does not receive a push channel.

**Key architectural principle:** Push notifications are an optional optimization for platforms that support them. macOS does not need push because it polls reliably at 60-second intervals.

---

## Architecture

### Why No Push Channel?

The `derive_push_channel()` function in `backend/src/homepot/app/schemas/os_capabilities.py` explicitly returns `None` for macOS:

| Platform | Push Channel | Protocol |
|----------|-------------|----------|
| Android | `fcm` | Firebase Cloud Messaging |
| Windows | `wns` | Windows Notification Service |
| iOS | `apns` | Apple Push Notification service |
| **macOS** | **`None`** | **HTTP Polling** |
| Linux | `None` | HTTP Polling |
| IoT/MQTT | `mqtt` | MQTT Protocol |

### Command Flow Diagram

```
┌──────────────────────────────┐                              ┌─────────────────────────┐
│         BACKEND              │                              │    macOS DEVICE         │
│                              │         HTTP Polling         │                         │
│  POST /devices/{id}/commands │ ◄─────────────────────────── │  Agent Runtime          │
│  (queue command)             │                              │  - heartbeat_loop()     │
│         │                    │                              │  - telemetry_loop()     │
│         ▼                    │                              │  - pending_commands_    │
│  DeviceCommand (PENDING)     │ ──── GET /devices/pending ── │    loop()               │
│         │                    │                              │                         │
│         │                    │ ◄──── POST .../ack ──────── │  ACK command            │
│  DeviceCommand (SENT)        │                              │                         │
│         │                    │                              │  Execute command        │
│         │                    │ ◄──── PUT .../status ────── │  Report result          │
│  DeviceCommand (COMPLETED)   │                              │                         │
│                              │                              │  IPC server (localhost) │
│  push_channel: None          │                              │  (real device app)      │
│  push_token: None            │                              │                         │
│                              │                              │  OS Elevation Layer     │
│  No push notification sent   │                              │  (homepot-ctl + sudo)   │
│  for macOS devices           │                              │                         │
└──────────────────────────────┘                              └─────────────────────────┘
```

---

## Key Files

| File | Role |
|------|------|
| `backend/src/homepot/app/schemas/os_capabilities.py` | OS classification, capabilities, push channel derivation |
| `backend/src/homepot/agent/real_device_agent.py` | Real agent runtime — heartbeat, telemetry, command polling loops |
| `backend/src/homepot/agent/utils/command_poller.py` | Command polling, permission gating, macOS-specific appliers |
| `backend/src/homepot/agent/utils/elevation.py` | Scoped sudo via `homepot-ctl` helper |
| `backend/src/homepot/agent/credential_storage.py` | Platform-aware storage — macOS uses Keychain or file |
| `backend/src/homepot/push_notifications/wakeup.py` | Wake-up sender — skips macOS since `push_channel` is None |
| `backend/src/homepot/app/api/API_v1/Endpoints/DeviceCommandsEndpoint.py` | API for queuing/polling/acking/reporting commands |

---

## OS Capabilities

macOS is grouped with Linux and receives **all capabilities enabled** (`os_capabilities.py:60-89`):

```python
{
    "root_access": True,
    "command_execution": True,
    "process_monitoring": True,
    "filesystem_access": True,
    "network_monitoring": True,
}
```

This means macOS devices can execute privileged operations (restart, shutdown, script execution) through the scoped elevation layer.

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

### Server-Side Wake-Up Attempt

When a command is queued (`DeviceCommandsEndpoint.py:152-155`):

```python
await send_command_wakeup(device)
```

The `send_command_wakeup()` function (`wakeup.py:71-128`) checks `device.push_channel` and `device.push_token`. For macOS: `push_channel` is `None`, so the function returns immediately — no push notification is sent.

---

## macOS-Specific Features

### OS Elevation Layer

macOS uses a scoped sudo mechanism via the `homepot-ctl` helper binary (`elevation.py`):

- **Installation:** Uses `osascript` (macOS) with an admin prompt
- **Scope:** Creates a NOPASSWD sudoers drop-in for `restart`, `shutdown`, `exec` operations
- **Security:** Autonomous teardown when `root_access` is revoked
- **Usage:** Free-form commands (`run_command`, `run_script`) require `root_access` permission and execute through this helper

### Credential Storage

On macOS (`sys.platform == "darwin"`), the credential storage factory (`credential_storage.py`) tries:

1. **`KeyringCredentialStorage`** — Uses macOS Keychain via the `keyring` library
2. **`MacOSFileStorage`** — Falls back to `~/Library/Application Support/Homepot/credentials` with `0o600` permissions

### macOS-Specific Command Appliers

The command poller (`command_poller.py:589-609`) includes macOS-specific implementations:

| Command | Implementation |
|---------|---------------|
| `brightness` | Uses Homebrew's `brightness` helper (`brew install brightness`) |
| `volume` | Uses `osascript -e 'set volume output volume <value>'` |

### Device Recovery (Start at Login)

Packaged builds of the User App register a **macOS login item** (`real-device-transition.md:95-113`):

- Auto-enabled on first launch
- Starts hidden in the tray
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

### Credential Security

- macOS uses Keychain (via `keyring` library) or file with strict `0o600` permissions
- Per-run IPC bearer token (random `secrets.token_urlsafe(32)`) for localhost IPC endpoints

---

## Comparison with Push-Based Platforms

| Aspect | macOS (Polling) | iOS/Android/Windows (Push) |
|--------|----------------|---------------------------|
| **Command delivery** | Device polls every 60s | Push notification triggers immediate poll |
| **Latency** | Up to 60 seconds | Near-instant (< 5 seconds) |
| **Network dependency** | Requires outbound HTTP | Requires push service connectivity |
| **Battery impact** | Moderate (periodic polling) | Low (push is event-driven) |
| **Implementation complexity** | Simple polling loop | Platform-specific push SDK integration |
| **Offline behavior** | Commands queue until next poll | Commands queue until push delivery |

---

## Testing

### macOS POS Emulator

A macOS POS emulator is available for testing (`emulators/macos_pos_emulator.py`):

```bash
./scripts/start-emulator.sh --site-id site-it-demo1 --bootstrap-key <key> --device-name demo-mac-pos-1
```

The emulator:
- Uses `os_details: "macOS 14"` and `device_type: "pos_terminal"`
- Gets full *nix permission capability map
- Runs as a thin wrapper around the shared `pos_engine.py`

### Manual Testing

To test command execution on a real macOS device:

1. Register the device via the Dashboard or API
2. Queue a command: `POST /api/v1/devices/{device_id}/commands`
3. Wait for the next polling interval (up to 60 seconds)
4. Verify the command is ACKed and executed
5. Check the result is reported back

---

## Summary

macOS device management in HOMEPOT is polling-based by design:

- **No push channel** — macOS relies entirely on HTTP polling (60s interval)
- **Full capability set** — All permissions including `root_access` enabled
- **Platform-native tooling** — `osascript` for volume, `brightness` helper for screen brightness
- **Secure elevation** — Scoped sudo via `homepot-ctl` helper
- **No third-party push SDK** — The entire push system is custom; macOS simply doesn't use it

This architecture trades some latency (up to 60s) for simplicity and reliability — macOS devices don't need push infrastructure to receive commands.
