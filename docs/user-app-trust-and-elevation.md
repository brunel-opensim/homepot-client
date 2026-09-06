# User App Trust Model & OS Elevation (Real Devices)

This document records the intended trust model for **real devices**, the
separation between consent and operating-system privilege, and what is
implemented today versus what is still missing. It complements
`agent-permissions-trust-model.md` (the consent model) and
`userapp-os-interaction-testing.md` (the OS interaction runbook).

## The model in one statement

Installing the User App is a one-time **owner approval**. It does **not** grant
the HOMEPOT platform any privileges. The Monitor/Manage trust model is a
separate, revocable layer that comes **after** installation: the device owner
decides, continuously, whether technicians may monitor or manage the device —
down to whether a command may run with root.

Root by inheritance is explicitly rejected: the app/agent must **not** run as
root or be granted blanket elevation at install time. Elevation must be
scoped to specific operations and tied to the consent lifecycle.

## Two separate layers

| Layer | What it is | Where it lives | Revocable? |
|---|---|---|---|
| **Consent (logical)** | `device_permissions` flags (`root_access`, monitor keys) that decide whether the platform may *attempt* a privileged operation | Backend database | Yes — owner toggles it in the User App; operator `admin-override` can revoke |
| **Elevation (physical)** | The OS-level capability that actually lets a command run elevated (`sudo -n`, a privileged helper, an entitlement) | The device operating system | **Today: not wired** — configured manually, never tied to consent |

These two layers are deliberately decoupled:

```
Manage toggle ──▶ backend device_permissions.root_access = true   (consent; OS unaware)
actual root ──▶  sudo -n -- <command>  at execution time           (needs pre-configured OS sudo/helper)
```

Granting consent therefore authorises the **attempt**; the OS decides the
actual privilege based on its own configuration.

## What exists today

### Consent plane (implemented)

- Device owner grants/revokes Monitor and Manage in the User App
  (`PATCH /devices/device/{id}/permissions`, device-credential auth).
- Backend rejects commands whose required permission is not granted **before**
  queueing (`required_permissions_for_command`), and the agent re-checks
  **before** executing.
- Operators may revoke but never grant (`admin-override` is revoke-only).
- Permissions and command history are audited.

### Data plane (unconditional by design)

- Once installed/provisioned, the User App's agent pushes telemetry, logs,
  audit events and alerts on its own cadence (device credentials only).
- The Dashboard reads that data with site access. No consent is consulted in
  the data-plane path — data flows into the Dashboard simply because the User
  App is installed.
- Consent governs the **command plane** only: on-demand diagnostics
  (Monitor) and elevated/host-modifying operations (Manage).

### Elevation at execution (partially stubbed)

- On POSIX the agent runs privileged commands through `sudo -n -- <argv>`
  (`command_poller.py` `_elevation_prefix`); on Windows via an assumed
  elevated service (no suffix).
- Non-interactive `sudo -n` fails cleanly when the agent's OS user has no
  passwordless (NOPASSWD) rule.

## What is missing (gaps)

| # | Gap | Today's behaviour | Required to close it |
|---|---|---|---|
| 1 | OS elevation is not provisioned by the app | Manage commands `failed` unless sudo/helper was configured manually | One-time, owner-elevation setup at claim/grant time: write a **scoped** `/etc/sudoers.d/homepot` NOPASSWD rule for the agent user, or install a privileged helper (LaunchDaemon / `SMJobBless`) with a narrow authenticated IPC surface |
| 2 | Revoking Manage does not remove OS capability | Toggling off stops backend dispatch (commands 403), but the sudoers rule/helper entry, if any, persists | Tie the OS elevation to the consent lifecycle — revoking Manage removes the rule/helper, not just the backend flag |
| 3 | No privileged-helper channel | Privileged commands run in-process via `sudo -n` | Introduce a small root helper exposed to the app over IPC, keeping the agent itself unprivileged (preferred, audit-friendly) |
| 4 | Mobile platforms cannot honour `root_access` | Capability table already marks `root_access` ✗ on iOS/Android | Keep elevation desktop/server-only; expose the Manage tier only where the OS supports it |

## Recommended elevation design

- **Never install the app/agent as root.** The agent runs as the logged-in
  user (or a dedicated `homepot` system user).
- Prefer a **privileged helper** (a `launchd` LaunchDaemon or systemd-style
  helper binary that runs as root and exposes a tiny, authenticated command
  interface) over broad sudo. If sudo is used, scope the NOPASSWD rule to
  HOMEPOT's command set — **not** `ALL`:
  ```
  homepot ALL=(ALL) NOPASSWD: /usr/bin/shutdown, /usr/bin/reboot, ...
  ```
- **Provision elevation only when the owner grants Manage**, under a fresh
  owner-elevation prompt, and **tear it down when Manage is revoked**.
- Keep the two tiers intact: Monitor = read-only diagnostics (no elevation
  needed), Manage = scoped elevation only.

## Why this is MDM-aligned

This is the standard least-privilege pattern used by MDM/fleet vendors:

- Owner approves **installation** (on Apple platforms this is the MDM
  User-Consent / profile approval).
- Privileged operations go through a **narrow, controlled elevation channel**
  (helper or scoped sudoers), not blanket root by inheritance.
- The agent runs unprivileged; a well-scoped helper holds the least privilege
  needed.
- Grants are **revocable** — taking the grant away must stop the capability.