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

Technician commands and scripts require `command_execution`. When a command or
script sets `run_as_root: true`, it additionally requires `root_access`. Root
execution uses non-interactive `sudo`; an unavailable or disallowed sudo policy
fails the command rather than prompting on the device.

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
