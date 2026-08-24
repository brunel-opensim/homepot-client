# User App ↔ Host OS Interaction

## Overview

The User App is a **self-contained application installed on the device or
system it manages** — today a Mac, later a Windows desktop or an Android POS.
The app must be able to:

- receive commands, scripts and instructions pushed from the backend;
- execute them against the host OS it runs on (within the two
  owner-facing permission tiers: **Monitor** and **Manage**);
- report results back so the Dashboard reflects reality.

This document separates the problem into two layers — **delivery** (how a
command travels from the backend to the device) and **local dispatch** (how the
installed app hands a command to the OS) — and records the chosen pattern.

## The two layers

### 1. Delivery layer (backend → device)

How a command gets from the server to the installed app. Three mechanisms:

| Mechanism | How it works | Best for |
|---|---|---|
| **HTTP polling** | The app polls `GET /devices/pending` on an interval and executes whatever is queued | Baseline; works on every OS with no external dependency (this is how macOS/Linux work today) |
| **App push** | OS push service delivers a wake-up to the app (FCM / WNS / APNs / MQTT) | Near-instant delivery + battery-friendly on mobile/POS runtimes |
| **MDM** | Device is enrolled in a device-management server; the server sends OS-level commands over the platform's MDM channel | Zero-touch enrollment and OS-level control (restart/shutdown/lock/erase) on managed fleets |

The backend already models the per-OS push channel
(`derive_push_channel` in `emulators/pos_engine.py`, mirrored by the backend's
`derive_capabilities` in `schemas/permissions.py`) and ships working providers
(`fcm_linux.py`, `wns_windows.py`, `apns_apple.py`, `mqtt_push.py`,
`simulation.py`).

### 2. Local dispatch layer (on-device)

How the installed app hands a received command to the host OS. IPC is **here**,
not on the delivery path:

- The User App is an Electron shell. It owns a small **local dispatch service**
  and talks to it over IPC — the context-isolated `ipcMain`/preload bridge
  already in `user_app/electron/main.ts`.
- The renderer never talks to the OS directly; every privileged action goes
  through the main process, which performs the OS call and returns the result.

#### Decision: the local dispatch engine is the bundled Python agent

The User App reuses the **bundled Python device agent**
(`homepot.agent.real_device_agent` → `command_poller.process_command`) as a
background child process, rather than reimplementing command execution in
TypeScript. This reuses the real execution for all nine command types
(including the OS settings adapter and `sudo` handling) and the permission
gating, and matches how the app already spawns Python emulators.

- **Spawn**: Electron main runs
  `python -m homepot.agent.real_device_agent` with
  `PYTHONPATH=<repo>/backend/src` and `HOMEPOT_AGENT_CONFIG=<config>`.
- **Config**: Electron writes `~/.homepot/agent/agent-config.json` from the
  stored credentials (`device_id`, `api_key`, `site_id`, `device_type`,
  `os_details`) and resolves `backend_url` from `HOMEPOT_BACKEND_URL` →
  stored `backend_url` → `http://localhost:8000/api/v1`.
- **Credentials handoff**: the agent's `create_credential_storage()` reads the
  same `~/.homepot/credentials` file Electron writes, so provisioned values
  are consistent either way.
- **Lifecycle**: Electron auto-starts the agent on launch when provisioned
  (`enrollment_method !== 'emulated'`, which keeps using the emulator), stops
  it on quit, and exposes `agent:start` / `agent:status` / `agent:stop` IPC.
- The agent then runs registration, heartbeat, telemetry, the pending-command
  loop (poll → permission re-check → `process_command` → report), and a
  watchdog — exactly the on-device command loop the User App needs.

## Platform channel matrix

| Target OS | App push | MDM option | Baseline |
|---|---|---|---|
| macOS | APNs (Developer ID app, bundle ID + push entitlement/cert) | Apple MDM over APNs — OS-level commands + zero-touch (Automated Device Enrollment) | HTTP polling |
| Windows | WNS (requires package identity / AUMID) | Windows MDM / OMA-DM (Pro/Enterprise) | HTTP polling |
| Android POS | FCM (first-class; already modeled) | Android Enterprise device-owner / DPC — privileged device admin | HTTP polling |
| Linux | — | — | HTTP polling |

## Command & script delivery: push as wake-up, pull as payload

**Rule: a push carries only a minimal reference; the authoritative command is
always pulled.** Do not embed scripts or instructions inside a push payload.

Rationale:

- Push payloads are size-limited (FCM / APNs ≈ 4 KB; WNS ≈ 5 KB). Scripts and
  firmware URLs routinely exceed this.
- Commands and scripts are sensitive; keeping them out of push channels means
  they are never logged by third-party push providers.
- The backend already stores every command in `DeviceCommand` and the agent
  pulls it via `GET /devices/pending`; `PushWakeupListener` already exists to
  wake the agent so it polls immediately.

### Sequence

```
1. Operator queues a command in the Dashboard / API
   -> backend stores a DeviceCommand (command_id, type, payload) with status=queued
2. Backend sends a minimal push wake-up to the device token
   data: { "device_id": ..., "command_id": ..., "collapse_key": <command type> }
   (falls back to plain polling when the device has no push channel)
3. The installed app receives the wake-up and pulls the pending command
   GET /devices/pending          (device-credential authenticated)
4. The local dispatch service re-checks device_permissions
   - Monitor tier -> command_execution / process_monitoring / network_monitoring
   - Manage tier  -> root_access (commands/scripts, scan_filesystem,
                     update_config, restart, shutdown) always via sudo
5. The dispatch service executes against the host OS
   - renderer -> IPC -> main process -> OS call
6. The app reports the terminal result
   PUT /devices/{command_id}/status  { status, executed_at, result }
```

Because the authoritative state is the queued command, this works even when a
push never arrives: polling picks up the command on the next interval, and
`ttl_seconds` / `collapse_key` govern expiry and de-duplication.

## Worked example: "increase brightness" on a Mac

Assumes the owner has granted **full manage access** (`root_access`) and the
Dashboard is synced. The command is an `update_config` with a `brightness`
key, traced end-to-end against what is built today:

| Step | What happens | Status |
|---|---|---|
| 1. Dashboard compose | `PushReview.jsx` → **Apply Configuration** (`update_config`), sets `brightness`; required group = **Manage device**, granted → **Queue Command** | ✅ built |
| 2. Backend queue + gate | `DeviceCommandsEndpoint` computes `required_permissions_for_command` → `["root_access"]`, checks the owner grant, creates `DeviceCommand` (`queued`) + audit | ✅ built |
| 3. Delivery | The **emulator** polls `GET /devices/pending` (15s). The **User App itself has no pending-command loop** and no real APNs token/wake-up yet | ⚠️ polling only |
| 4. On-device permission re-check | `command_poller._check_permission` re-verifies `root_access` — exists in the Python agent, not in the Electron app | ⚠️ agent only |
| 5. Execute brightness on macOS | `process_command("update_config")` currently only records `applied_keys` ("config update acknowledged") — **no real brightness call** | ❌ gap |
| 6. Report result | `PUT /devices/{id}/status` with `{status, executed_at, result}` — done by the agent/emulator, not the User App | ⚠️ agent only |
| 7. Dashboard reflects result | Command History / Push History renders the terminal status | ✅ built |

### Gaps for this example

1. **The User App must run the on-device command loop** — poll pending →
   re-check permission → execute → report. Today only the emulator / separate
   Python agent does this.
2. **`update_config` execution is a stub** — it needs a real **OS settings
   adapter** that maps keys (e.g. `brightness`) to actual OS calls
   (`brightness <level>`, `osascript`/IOKit on macOS), run with the appropriate
   privilege (sudo for system prefs).
3. **Real push delivery** (optional Phase 1) — APNs token registration +
   wake-up listener in Electron; otherwise rely on polling.

## Execution maturity

The backend agent's `process_command` (`command_poller.py`) is not yet complete
for every command type. Status as of writing:

| Command type | Tier | Execution status |
|---|---|---|
| `run_command` | Manage | ✅ real (subprocess + `sudo`) |
| `run_script` | Manage | ✅ real (subprocess + `sudo`) |
| `ping` / `status_request` | — | ✅ real |
| `update_config` | Manage | ❌ stub — records `applied_keys`, no OS call |
| `restart` / `shutdown` | Manage | ❌ stub — acknowledged, not executed |
| `health_check` | Monitor | ❌ unhandled (`Unhandled command type`) |
| `list_processes` | Monitor | ❌ unhandled |
| `list_connections` | Monitor | ❌ unhandled |
| `scan_filesystem` | Manage | ❌ unhandled |

The emulator (`pos_engine.py`) simulates all nine, but the real agent only
executes `run_command`/`run_script` against the host today. Closing these gaps
is the "local execution" work that makes a self-contained User App real.

## MDM decision

Treat MDM as a **Phase 2 complement**, not a Phase 1 requirement:

- The nine commands (diagnostics, monitoring, command/script execution,
  config/firmware, reboot, shutdown) are all deliverable through app push +
  polling and gated by the Monitor/Manage tiers we already built.
- MDM's unique value is **zero-touch enrollment** (provision the app without a
  human) and **OS-level control beyond sudo** (e.g. locked kiosk reboot,
  remote lock/wipe, managed settings on a device with no user session).
- MDM adds real infrastructure: certificates/keys, an MDM server or provider,
  enrollment profiles, and per-OS protocol support.

Recommended path: ship self-contained with app push (APNs/WNS/FCM) + polling
first; add MDM when the fleet needs managed enrollment or kiosk-locked control.

## Implementation checklist

Backend:

- [x] Permission tiers + command→permission mapping (Monitor / Manage).
- [ ] Complete `process_command` execution: `health_check`, `list_processes`,
      `list_connections`, `scan_filesystem`, and a real `update_config` OS
      settings adapter; wire real `restart` / `shutdown`.
- [ ] Real `device_token` registration (store per-device token + channel on
      registration / status report).
- [ ] Wake-up sending: after queueing a `DeviceCommand`, send the minimal
      wake-up via the resolved provider; no-op for polling-only devices.
- [ ] APNs / WNS credentials (certificate/key, bundle/AUMID) and FCM service
      account wiring.

User App (Electron main):

- [x] **On-device command loop**: resolved by bundling the Python device agent
      (spawn via `HOMEPOT_AGENT_CONFIG` + `PYTHONPATH`; it polls `GET /devices/pending`,
      re-checks `device_permissions`, executes, reports `PUT /devices/{id}/status`).
- [x] **Local dispatch service**: Electron main spawns the agent, auto-starts it
      when provisioned, stops it on quit; `agent:start` / `agent:status` /
      `agent:stop` IPC handlers.
- [ ] Wake-up listener per platform (FCM/WNS/APNs) that triggers a
      `GET /devices/pending` pull; polling interval as fallback.
- [ ] Map the nine command types to OS calls per tier (Monitor read-only;
      Manage via `sudo`). — done in `command_poller.process_command`, reused by
      the bundled agent.

Docs:

- [x] This page linked from the User App nav.
- [ ] Record the final decision once Phase 2 (MDM) is scoped.

## Open questions

- Should the local dispatch service be embedded Node (TS) or the bundled
  Python agent? → **Resolved: bundled Python agent** (reuses `process_command`
  execution, permission gating, and the emulator-spawn pattern).
- Does Windows POS need a packaged identity for WNS, or will it poll?
- Which MDM provider (if any) targets macOS and Windows fleets first?