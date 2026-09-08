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
| **Consent (logical)** | `device_permissions` flags (`root_access`, monitor keys) that decide whether the platform may *attempt* a privileged operation | Backend database | Yes — owner toggles it in the User App; operator `admin-override` is revoke-only |
| **Elevation (physical)** | The OS-level capability that actually lets a command run elevated (`sudo -n`, a privileged helper, an entitlement) | The device operating system | **Yes** — provisioned and torn down by the User App, tied to the consent lifecycle |

These two layers are deliberately decoupled **in the backend**, but the User App
now couples them **on the device**:

```
Manage toggle ──▶ backend device_permissions.root_access = true     (consent; OS unaware)
              └─> User App installs scoped elevation (homepot-ctl +  (physical)
                  /etc/sudoers.d/homepot NOPASSWD drop-in) under a
                  one-time macOS admin prompt
actual root ──▶  sudo -n /usr/local/homepot/homepot-ctl run <op>      (scoped, at execution time)
```

Granting consent therefore authorises the **attempt**; the OS decides the
actual privilege based on its own configuration — and revoking consent now
tears the OS capability back down.

## Permission toggles (owner-facing groups)

The User App exposes two toggles that map onto the capability keys:

- **Monitor** — a group: `command_execution`, `process_monitoring`,
  `filesystem_access`, `network_monitoring`. Read-heavy diagnostics and
  introspection; no OS elevation.
- **Manage** — `root_access`. Scoped elevated/host-modifying operations only.

Only the **device owner** can grant or revoke these. The Dashboard can only
**request** a grant; operators may revoke (never grant) via `admin-override`.

## What exists today

### Consent plane (implemented, verified)

- Device owner grants/revokes Monitor and Manage in the User App
  (`PATCH /devices/device/{id}/permissions`, device-credential auth).
- Toggling off is picked up on the agent's next permission poll (~15–30 s).
- Backend rejects commands whose required permission is not granted **before**
  queueing (`required_permissions_for_command` → 403 listing
  `missing_permissions`), and the agent re-checks **before** executing.
- Operators may revoke but never grant (`admin-override` is revoke-only).
- Permissions and command history are audited.

### Elevation plane (implemented, verified on a real Mac)

- When the owner grants **Manage**, the User App runs a one-time macOS admin
  prompt and provisions scoped elevation:
  - `/usr/local/homepot/homepot-ctl` (0755, root:wheel) — a small helper the
    agent invokes via `sudo -n` for allowlisted operations;
  - `/etc/sudoers.d/homepot` (0440, root:wheel) — a NOPASSWD drop-in scoped
    **only** to `homepot-ctl`, never `ALL`.
- The drop-in is verified narrow: `sudo -n cat /etc/sudoers.d/homepot` still
  prompts for a password, while `sudo -n homepot-ctl status` runs passwordless.
- `homepot-ctl status` reports `{"installed","provisioned","allowlist"}`; the
  elevation state is surfaced in agent logs.
- When the owner revokes **Manage**, the agent deprovisions **autonomously**:
  the drop-in (and allowlist) is removed. The `homepot-ctl` binary remains on
  disk — `homepot-ctl status` → `{"installed":"yes","provisioned":"no","allowlist":"no"}`.

### Command plane (three enforcement layers)

1. **Dashboard request gate** — a push whose group is not granted renders as a
   "Request Access" button, not a Send.
2. **Backend queue-time permission gate** — required permission missing ⇒ 403
   before the command is ever queued.
3. **Agent allowlist/resolution layer** — commands that do pass still resolve
   against the host OS: free-form `run_command`/`run_script` are refused even
   when `root_access` is granted (only predefined operations —
   `restart`/`shutdown` — can be elevated), and each command is re-checked
   against the permission set fetched at execution time.

### Operational exit strategy (cancel)

- A stuck/abandoned command (`pending`/`sent`) can be **cancelled** by an
  operator: `POST /api/v1/devices/{device_id}/commands/{command_id}/cancel`.
- Cancelling moves the command to a terminal `cancelled` state (with operator
  identity and timestamp), stored via the same status-update path as any other
  terminal state. Idempotent on terminal states.
- The Dashboard exposes a Cancel button (and styled confirmation dialog) on
  in-flight commands.

### Data plane (unconditional by design)

- Once installed/provisioned, the User App's agent pushes telemetry, logs,
  audit events and alerts on its own cadence (device credentials only).
- The Dashboard reads that data with site access. No consent is consulted in
  the data-plane path — data flows into the Dashboard simply because the User
  App is installed.
- Consent governs the **command plane** only: on-demand diagnostics
  (Monitor) and elevated/host-modifying operations (Manage).

## Verified end-to-end (real device, macOS "This Laptop")

Recorded evidence from a live run against `DEVICE-P9CQ-TTBX-NFPJ`:

1. **Monitor grant** → capabilities derived correctly once the backend's
   `os_family` recognised `os_details: "mac"`; command/permissions endpoints
   returned the granted set (`root_access: false`, monitor keys `true`).
2. **Manage grant** → one-time admin prompt; drop-in and helper installed with
   the exact scoped permissions above; `sudo -n homepot-ctl status` →
   `{"installed":"yes","provisioned":"yes","allowlist":"yes"}`.
3. **Allowlist refusal** → a free-form `run_command` was acked then refused
   with *"free-form command execution is not allowlisted on this device's OS;
   only predefined power operations (restart/shutdown) can be elevated"*, and
   the command landed in the Dashboard as `failed` (status reported via PUT —
   an earlier POST → 405 transport bug was fixed).
4. **Cancel** → the stuck `sent` command was cancelled end-to-end via the
   Dashboard dialog; history shows `cancelled` with operator + timestamp.
5. **Manage revoke** → `/etc/sudoers.d/homepot` removed autonomously;
   `homepot-ctl status` → `provisioned: no, allowlist: no`; backend
   `root_access: false`; the agent's "elevation not provisioned" warning
   ceases.
6. **Monitor revoke** → Dashboard flips to "Request Access"; backend rejects
   `list_processes` at queue time (`missing_permissions: ["process_monitoring"]`).
7. **Monitor re-grant** → `list_processes` queued, acked, executed and returned
   the live process table (863 processes on the test Mac) via `PUT /status 200`.

## What is missing (gaps)

| # | Gap | Today's behaviour | Required to close it |
|---|---|---|---|
| 1 | ~~OS elevation not provisioned by the app~~ | **Closed** — User App provisions scoped `homepot-ctl` + `/etc/sudoers.d/homepot` NOPASSWD drop-in on Manage grant (one-time owner admin prompt) | — |
| 2 | ~~Revoking Manage does not remove OS capability~~ | **Closed** — owner revoke triggers autonomous deprovision that removes the drop-in and allowlist (binary intentionally retained) | — |
| 3 | No privileged-helper channel | Privileged commands run in-process via `sudo -n homepot-ctl` | Introduce a small root helper (LaunchDaemon / `SMJobBless`) exposed over IPC, keeping the agent itself unprivileged (preferred, audit-friendly) |
| 4 | Mobile platforms cannot honour `root_access` | Capability table already marks `root_access` ✗ on iOS/Android | Keep elevation desktop/server-only; expose the Manage tier only where the OS supports it |

## Recommended elevation design

- **Never install the app/agent as root.** The agent runs as the logged-in
  user (or a dedicated `homepot` system user).
- Prefer a **privileged helper** (a `launchd` LaunchDaemon or systemd-style
  helper binary that runs as root and exposes a tiny, authenticated command
  interface) over broad sudo. If sudo is used, scope the NOPASSWD rule to
  HOMEPOT's command set — **not** `ALL` (as the current drop-in does):
  ```
  homepot ALL=(ALL) NOPASSWD: /usr/local/homepot/homepot-ctl
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
- Grants are **revocable** — taking the grant away must stop the capability
  (verified: revoking Manage removes the sudoers drop-in, not just the backend
  flag).