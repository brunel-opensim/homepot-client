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
  (embedded Node code, or the bundled Python agent) and talks to it over IPC —
  the context-isolated `ipcMain`/preload bridge already in
  `user_app/electron/main.ts`.
- The renderer never talks to the OS directly; every privileged action goes
  through the main process, which performs the OS call (`child_process`,
  `sudo`, filesystem, reboot/shutdown) and returns the result.

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

- [ ] Real `device_token` registration (store per-device token + channel on
      registration / status report).
- [ ] Wake-up sending: after queueing a `DeviceCommand`, send the minimal
      wake-up via the resolved provider; no-op for polling-only devices.
- [ ] APNs / WNS credentials (certificate/key, bundle/AUMID) and FCM service
      account wiring.

User App (Electron main):

- [ ] Local dispatch service over IPC (`ipcMain` handlers that execute commands
      against the host and return results).
- [ ] Wake-up listener per platform (FCM/WNS/APNs) that triggers a
      `GET /devices/pending` pull; polling interval as fallback.
- [ ] Map the nine command types to OS calls per tier (Monitor read-only;
      Manage via `sudo`).

Docs:

- [ ] This page linked from the User App nav.
- [ ] Record the final decision once Phase 2 (MDM) is scoped.

## Open questions

- Should the local dispatch service be embedded Node (TS) or the bundled
  Python agent? (Embedded TS keeps the app single-runtime; the Python agent
  reuses `command_poller`'s sudo/execution logic today.)
- Does Windows POS need a packaged identity for WNS, or will it poll?
- Which MDM provider (if any) targets macOS and Windows fleets first?