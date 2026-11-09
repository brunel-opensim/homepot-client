# Restart Agent Command (Design)

Status: Proposed (not yet implemented)

> Decision: "Restart the User App" resolves to **restarting the agent** (the
> backend-communication child process), not the whole Electron shell. See
> "Why agent, not whole app" below.

## Problem

The Dashboard can ask a device to reboot (`restart`), shut down (`shutdown`),
or restart a named OS service (`restart_service`). It cannot ask the device to
restart the **agent** — the process that actually talks to the backend.

The User App is an Electron desktop application that spawns the Python
`homepot-agent` as a child process. Neither is an OS service, so none of the
existing command types apply:

| Command | Effect | Why it does not restart the agent |
|---|---|---|
| `restart` | Reboots the whole device | Full OS reboot, not a targeted agent restart |
| `restart_service` | Restarts a named OS service | The agent is not a service |
| `shutdown` | Shuts the device down | Opposite of restarting the agent |

The only "restart" today is automatic: the Electron supervisor
(`user_app/electron/agentSupervisor.ts`) respawns the agent on an unexpected
exit (bounded to three in five minutes), and the agent's watchdog restarts it on
a hang. There is no **technician-initiated, remote** restart.

## Goal

Add a `restart_agent` command so the Dashboard (or the AI) can ask a real device
to restart its agent process — a manual "bounce" for a device that is **online
but misbehaving** (stale telemetry, hung command, erroring agent) that the
automatic supervisor/watchdog has not caught.

## Why agent, not whole app

A technician operates from the Dashboard (web) and never sees the device's
on-device window. The only part of the User App they can observe — and therefore
care about — is the **agent** (heartbeat, telemetry, command execution). The
Electron shell is invisible to them, so restarting it adds nothing useful
remotely. "Restart the agent" is the precise action for the remote-management
scenario.

## Important limitation (set expectations honestly)

The command is delivered **by the agent polling** the backend, so it only works
when the agent is still alive and polling. It is a **soft recovery** for an
online-but-misbehaving agent, **not** a rescue for a fully-offline device. A
device with no heartbeat cannot receive this command; that still needs physical
access or a push-wake mechanism (a separate feature).

## Design

### 1. New command type: `restart_agent`

- Risk tier T3 (disruptive), permission `root_access`, no parameters.
- Added to the device agent's `COMMAND_TYPES` and `REQUIRED_PERMISSION`.
- Added to the AI `ACTION_REGISTRY` (`ai/actions.py`), the Compose Command
  template (`PushReview.jsx`), and the command payload reference
  (`ai/system_knowledge.py`) so the AI, the manual dropdown, and the system
  prompt stay aligned.

### 2. Agent side (`command_poller.py` / `real_device_agent.py`)

- `_restart_agent()` returns a success result
  (`{"status": "completed", "result": {"message": "restart initiated"}}`) so the
  technician sees a clean success rather than a timeout.
- After the result is posted back to the backend, the agent exits with a
  **reserved exit code** (see below).

### 3. Electron side (`main.ts` / `agentSupervisor.ts`)

- In `child.on('exit')`, detect the reserved exit code and restart the agent
  cleanly: reset the crash-loop counter (this is not a crash) and call
  `startAgentProcess()` — without counting it against the supervisor's bounded
  restart budget.

## Communication channel (agent to Electron)

The agent is a child process; its exit code is the simplest, most unambiguous
signal for an agent-only restart.

| Option | Mechanism | Notes |
|---|---|---|
| **B. reserved exit code (recommended)** | Agent exits with a reserved code (for example 42) after posting its result; `on('exit')` maps it to a clean restart | No protocol ambiguity; cleanly bypasses the crash-loop counter |
| **A. stdout marker** | Agent writes a unique line such as `__HOMEPOT_RESTART_AGENT__`; the stdout handler detects it and restarts the agent | Works, but overkill for agent-only (better suited to a whole-app relaunch) |

Option B is preferred for agent-only restart: the agent posts "completed", then
exits with the reserved code, and the supervisor respawns it without treating it
as a crash.

## Edge cases

1. **Result-before-exit ordering** — the agent must POST the success result
   before exiting, otherwise the backend marks the command `expired`/`failed`.
2. **Crash-loop interaction** — the reserved exit code must reset (not
   increment) the supervisor's crash-loop counter.
3. **Watchdog** — the restart must not trip the agent's hang detector.
4. **Emulator / dev mode** — real-device only; the emulator has no Electron
   supervisor to respawn the agent.

## Scope of change

| Layer | Change | Effort |
|---|---|---|
| Backend (`command_poller.py`, `actions.py`, `system_knowledge.py`) | command type, handler, registry, reference | Small |
| Electron (`main.ts`, `agentSupervisor.ts`) | exit-code handling + clean respawn | Small |
| Frontend (`PushReview.jsx`) | Compose Command template entry | Small |
| Tests | command polling + supervisor | Moderate |
