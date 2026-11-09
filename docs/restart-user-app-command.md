# Restart User App Command (Design)

Status: Proposed (not yet implemented)

## Problem

The Dashboard can ask a device to reboot (`restart`), shut down (`shutdown`),
or restart a named OS service (`restart_service`). It cannot ask the device to
restart the **User App** itself.

The User App is an Electron desktop application that spawns the Python
`homepot-agent` as a child process. It is **not** an OS service (not a Windows
service, systemd unit, or launchd label), so none of the existing command types
apply:

| Command | Effect | Why it does not restart the app |
|---|---|---|
| `restart` | Reboots the whole device | Full OS reboot, not a targeted app restart |
| `restart_service` | Restarts a named OS service | The app is not a service |
| `shutdown` | Shuts the device down | Opposite of restarting the app |

The only "restart" the app does today is crash recovery: the Electron
supervisor (`user_app/electron/agentSupervisor.ts`) respawns the agent on an
unexpected exit, bounded to three restarts in five minutes. That is local crash
handling, not a remotely-triggered action.

## Goal

Add a `restart_app` command so the Dashboard (or the AI) can ask a real device
to restart the whole User App (Electron shell plus its agent child process).

## Design

### 1. New command type: `restart_app`

- Risk tier T3 (disruptive), permission `root_access`, no parameters.
- Added to the device agent's `COMMAND_TYPES` and `REQUIRED_PERMISSION`.
- Added to the AI `ACTION_REGISTRY` (`ai/actions.py`), the Compose Command
  template (`PushReview.jsx`), and the command payload reference
  (`ai/system_knowledge.py`) so the AI, the manual dropdown, and the system
  prompt stay aligned.

### 2. Agent side (`command_poller.py` / `real_device_agent.py`)

- `_restart_app()` returns a success result
  (`{"status": "completed", "result": {"message": "restart initiated"}}`) so the
  technician sees a clean success rather than a timeout.
- After the result is posted back to the backend, the agent signals the Electron
  shell (see the communication channel below).

### 3. Electron side (`main.ts`)

- Detect the agent's signal and reuse the existing restart path
  (`restartToApplySourceUpdate()`): stop the emulator and agent, then
  `app.relaunch()` + `app.exit(0)`.

## Communication channel (agent to Electron)

The agent is a child process whose stdout is already piped to Electron for
logging. Two options:

| Option | Mechanism | Notes |
|---|---|---|
| **A. stdout marker (recommended)** | Agent writes a unique line such as `__HOMEPOT_RESTART_APP__`; the Electron stdout handler detects it and relaunches | Reuses the existing log pipe; keeps the agent alive long enough to post its result |
| **B. reserved exit code** | Agent exits with a reserved code (for example 42); `on('exit')` maps it to relaunch instead of crash-restart | Cleaner semantics, but must bypass the crash-loop counter |

Option A is preferred: it lets the agent post "completed" first, then Electron
restarts everything.

## Edge cases

1. **Result-before-restart ordering** — the agent must POST the success result
   before triggering the restart, otherwise the backend marks the command
   `expired`/`failed` while the app restarts.
2. **Crash-loop interference** — an intentional restart must not be counted by
   `AgentSupervisor` as a crash (the stdout-marker path avoids this naturally).
3. **Watchdog** — the agent runs with `watchdog_enabled: true`; the restart must
   not trip the hang detector.
4. **Emulator / dev mode** — real-device only; the emulator has no Electron
   shell to restart.

## Scope of change

| Layer | Change | Effort |
|---|---|---|
| Backend (`command_poller.py`, `actions.py`, `system_knowledge.py`) | command type, handler, registry, reference | Small |
| Electron (`main.ts`) | stdout-marker detection + relaunch | Small |
| Frontend (`PushReview.jsx`) | Compose Command template entry | Small |
| Tests | command polling + supervisor | Moderate |

## Open decision

Whether "restart the User App" means:

- **Whole app** (Electron shell + agent) — matches the name; or
- **Agent only** (agent exits, the existing supervisor respawns it) — lighter,
  but the Electron shell stays up and the name is slightly misleading.

The design above assumes the whole-app interpretation.
