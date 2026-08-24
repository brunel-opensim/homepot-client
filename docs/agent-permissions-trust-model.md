# Agent Permissions & Trust Model

HOMEPOT manages heterogeneous devices across multiple OS platforms (Linux,
Windows, iOS, Android, etc.) under a single platform. The architecture
uses two complementary channels:

| Channel | Role | Auth | Scope |
|---|---|---|---|
| **Push Notifications** | Operational plane — deliver commands to devices (restart, update config, etc.) | Device API key | Works across all OS platforms, no user at terminal required |
| **User App** | Trust plane — device owner sees and consents to what the agent is allowed to do | Device API key + local UI | User-granted permission boundary |

## How they work together

```
  User App                    Backend DB                   Push Notification
 (trust plane)              (enforcement)                (operational plane)
      |                          |                              |
      |  PATCH /permissions      |                              |
      |  {root_access: true}     |                              |
      |------------------------->|                              |
      |                          | store device_permissions     |
      |                          |                              |
      |                          |     dispatch reboot cmd      |
      |                          |<-----------------------------|
      |                          |                              |
      |                          | check device_permissions     |
      |                          | root_access == true? ──yes──→ send to device
      |                          |                              |
```

The User App does **not** replace push notifications. The User App
**governs** what push notifications are allowed to do on that specific
device.

## Permission lifecycle

1. **Device provisions** (U2) — creates device record, `device_permissions`
   defaults to all `false`
2. **Device owner opens User App** → views current permissions on the
   `/permissions` page
3. **Owner toggles permissions** (U4) — `PATCH /devices/device/{id}/permissions`
   with device-credential auth
4. **Backend stores** the grant in `device_permissions` JSON column (U3)
5. **Push notification arrives** for a privileged operation (U5) — backend
   checks `device_permissions` before dispatching; if the required flag
   is `false`, the command is rejected at the API layer before it ever
   reaches the device
6. **Agent executes** only commands that pass the permission gate (U5)

Technician command and script execution is always elevated: it requires
`root_access` and runs through non-interactive `sudo`; an unavailable or
disallowed sudo policy fails the command rather than prompting on the device.

## Heterogeneous device handling

Each OS platform exposes different capabilities. The architecture handles
this through device-reported OS DNA (set at provision/registration time):

| OS | `root_access` | `command_execution` | `process_monitoring` | `filesystem_access` | `network_monitoring` |
|---|---|---|---|---|---|
| Linux | ✓ | ✓ | ✓ | ✓ | ✓ |
| Windows | ✗ | ✓ | ✓ | ✓ | ✓ |
| iOS (non-jailbroken) | ✗ | ✗ | ✗ | ✗ | ✓ |
| Android | ✗ | ✓ | ✓ | ✓ | ✓ |

A future capability-to-permission mapping layer will reject PATCH requests
for permissions the device's OS cannot support.

## Command-to-permission mapping

Each command type dispatched to a device requires a specific
`device_permissions` flag. The backend enforces this **before** queueing
(`required_permissions_for_command` in
`backend/src/homepot/agent/utils/command_poller.py`), and the agent
re-checks it **before** executing.

### Privileged commands

Commands are classified into **two owner-facing tiers**: read-only monitoring
(Monitor device) and elevated execution / system control (Manage device). All
command/script execution is elevated — it runs through `sudo` and is gated on
`root_access`.

| Command type | Required permission | Tier | Notes |
|---|---|---|---|
| `run_command` | `root_access` | Manage | always runs via `sudo` |
| `run_script` | `root_access` | Manage | always runs via `sudo` |
| `scan_filesystem` | `root_access` | Manage | full filesystem scan |
| `update_config` | `root_access` | Manage | config / firmware / settings |
| `restart` | `root_access` | Manage | reboot the host system |
| `shutdown` | `root_access` | Manage | power off the host system |
| `health_check` | `command_execution` | Monitor | self-tests / diagnostics |
| `list_processes` | `process_monitoring` | Monitor | view running processes |
| `list_connections` | `network_monitoring` | Monitor | view network connections |

### Non-privileged commands

`ping`, `status_request` and `request_permission` are allowed without a grant
(system / read-only).

### Dashboard Compose Command templates

| Template | Command type | Required permission |
|---|---|---|
| Run Command | `run_command` | `root_access` |
| Run Script | `run_script` | `root_access` |
| Apply Configuration | `update_config` | `root_access` |
| Reboot System | `restart` | `root_access` |
| Update Firmware | `update_config` | `root_access` |
| Run Diagnostics | `health_check` | `command_execution` |
| List Processes | `list_processes` | `process_monitoring` |
| List Network Connections | `list_connections` | `network_monitoring` |
| Scan Filesystem | `scan_filesystem` | `root_access` |
| Shut Down System | `shutdown` | `root_access` |

Every permission key now gates at least one command, so a grant in the
User App always enables something.

### User App presentation (owner-facing)

The User App presents permissions to the device owner as **two grouped
toggles** rather than the five raw keys — owners don't reason about the
per-command granularity, they decide whether the Dashboard may manage the
device and whether that may include root:

| User App toggle | Maps to permissions | Enables |
|---|---|---|
| **Allow Dashboard to monitor this device** | `command_execution`, `filesystem_access`, `process_monitoring`, `network_monitoring` | run diagnostics, view processes & network |
| **Allow Dashboard to manage this device** | `root_access` | run commands/scripts with sudo, scan the filesystem, update config/firmware, reboot or shut down the system (only available when monitoring is on) |

The backend still enforces the strict **per-command** permission checks; the
two-toggles are purely the owner-facing simplification. `root_access` is only
granted by the User App when managing is enabled.

## Command dispatch flow (end-to-end)

```
1. Operator creates job via Dashboard / API
2. Orchestrator selects target devices (by site, segment, etc.)
3. For each device:
   a. Check device_permissions for the required flag(s)
   b. If denied → log rejection, skip
   c. If granted → dispatch via push notification (FCM / APNs / WNS / MQTT)
4. Device agent receives push payload, executes within granted scope
5. Result flows back via heartbeat / telemetry
```

The backend checks grants before queueing and the agent checks them again before
acknowledging or executing. Operators may revoke permissions, but grants must
come from the device owner through the User App.

## Benefits of the split-plane design

- **Trust without friction** — device owner grants consent once in the
  User App; every subsequent push command respects that consent
- **Offline-capable** — permissions are stored server-side; push
  commands are gated at dispatch time, not at execution time
- **Cross-platform** — push notifications work on any OS; the User App
  adapts its UI per OS capabilities
- **Auditable** — every permission change and every command dispatch is
  logged
