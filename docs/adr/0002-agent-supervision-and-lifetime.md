# ADR-0002: Agent Supervision & Lifetime

- **Status:** Proposed
- **Date:** 2026-10-24

## Context

The Electron User App spawns the Python agent as a child process
(`startAgentProcess` in `user_app/electron/main.ts`). Today:

- `child.on('exit')` logs and clears the handle but never restarts the agent.
- `watchdog_enabled: true` in the agent config is a no-op on Windows
  (`_watchdog_loop` only emits `systemd.daemon.notify`).
- `killAgent()` sends `SIGTERM` then `SIGKILL` after 3 s, while the agent's own
  shutdown timeout is 30 s — so graceful shutdown (including the final OFFLINE
  heartbeat) is routinely cut short.

A crashed or killed agent leaves the device offline until the app is relaunched.
We need to decide where supervision lives.

## Decision drivers

- A real Windows device must come back online after: agent crash, OOM, AV kill,
  app quit/relaunch, and host reboot.
- The trust model installs the app **unprivileged**; elevated actions are scoped
  to the `homepot-ctl` helper (see
  [Trust Model & OS Elevation](../user-app-trust-and-elevation.md)). Supervision
  must not require a system-wide privileged service unless justified.
- Re-enrolment and unpair must be able to stop the agent *without* it being
  auto-restarted (an intentional-stop signal).

## Options considered

### A. Electron child-process supervisor

Electron restarts the agent on unexpected exit with a crash-loop backoff
(e.g. 3 restarts / 5 min, then surface an error to the operator). A flag
distinguishes intentional stops (unpair, re-enrol, quit) from crashes.

- **Pros:** no new privileged surface; lives where the app already manages the
  agent; simplest to ship; easy to surface status in the tray UI.
- **Cons:** agent only runs while the app runs; app crash also takes the agent
  down; relies on launch-at-login for reboot recovery.

### B. Standalone Windows service (SCM-managed)

Package the agent as a Windows service with automatic start and recovery.

- **Pros:** agent survives app quit/crash; native crash recovery; start on boot
  independent of the app.
- **Cons:** installation/elevation story changes; separate lifecycle from the app
  complicates re-enrolment/unpair (the app must talk to the service); more
  surface area for credential/config handoff.

### C. Hybrid (service + app supervision)

Service owns the long-lived agent; the app supervises only during provisioning/
re-enrolment transitions.

- **Pros:** best uptime.
- **Cons:** highest complexity; two supervisors to reconcile; premature for the
  current fleet size.

## Recommendation

Adopt **A (Electron child-process supervisor)** now, with a crash-loop backoff
and an explicit intentional-stop flag. It matches the existing unprivileged
trust model, fixes the immediate "crash = offline until relaunch" gap, and
requires no new privileged component. Revisit B/C only if fleet scale or
customer requirements demand app-independent agent uptime.

## Consequences

- **Easier:** agents self-heal from crashes; operators see a clear "agent
  restarting" state; no privileged install change.
- **Harder:** must carefully define the crash-loop policy (max restarts, backoff,
  reset window) and the intentional-stop signalling between the renderer and the
  main process.
- **Constrained:** agent lifetime is coupled to the app for now; boot-time
  recovery continues to rely on launch-at-login.
