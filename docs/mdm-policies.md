# MDM Policies (Mobile Device Management)

HOMEPOT supports Mobile Device Management (MDM)-style policies for controlling
device behavior, security posture, and application access. Policies are
delivered as device commands, executed by the on-device agent, and persisted
locally so they survive reboots.

## Overview

MDM policies allow technicians and the AI to remotely configure and enforce
security and operational rules on managed devices. Each policy is a device
command that:

1. Is composed from the Dashboard (PushReview page) or proposed by the AI.
2. Is queued on the backend and polled by the device agent.
3. Is executed locally by the agent (requires appropriate permissions).
4. Persists its configuration to `C:\ProgramData\Homepot\` (Windows) so it
   survives reboots.
5. Reports results back to the backend for audit and compliance.

## Policy categories

### 1. Application control

| Command | Permission | Tier | Description |
|---------|-----------|------|-------------|
| `set_app_policy` | `root_access` | T2 | Configure app allowlist/blocklist. Kills running instances of blocked apps and persists policy to `app_policy.json`. |

See [Set App Policy](set-app-policy.md) for full documentation.

**Modes:**
- **blocklist** — block specific apps (social media, games, browsers)
- **allowlist** — only allow specific apps (block everything else)

**Enforcement:** Process-level (kills running instances). OS-level enforcement
(AppLocker/WDAC on Windows, MDM profiles on macOS/iOS) is a future enhancement.

### 2. Network & connectivity

| Command | Permission | Tier | Status | Description |
|---------|-----------|------|--------|-------------|
| `set_wifi_policy` | `root_access` | T2 | Planned | Only connect to approved SSIDs. Auto-disconnect from unauthorized networks. |
| `set_vpn_policy` | `root_access` | T2 | Planned | Force VPN tunnel for all traffic. Block traffic if VPN drops. |
| `set_firewall_rules` | `root_access` | T2 | Planned | Configure host firewall: block/allow ports, protocols, IP ranges. |
| `set_dns_policy` | `command_execution` | T1 | Planned | Force DNS to a filtering resolver. |
| `disable_bluetooth` | `root_access` | T2 | Planned | Disable Bluetooth or restrict to paired devices. |
| `set_usb_policy` | `root_access` | T2 | Planned | Block USB mass storage; restrict to charging only. |

### 3. Security & hardening

| Command | Permission | Tier | Status | Description |
|---------|-----------|------|--------|-------------|
| `set_screen_lock_policy` | `root_access` | T2 | Planned | Enforce lock screen after N minutes of inactivity. Require PIN/password. |
| `enforce_encryption` | `root_access` | T2 | Planned | Require full-disk encryption (BitLocker/FileVault/LUKS). |
| `set_password_policy` | `root_access` | T2 | Planned | Min length, complexity, expiry, lockout after N failed attempts. |
| `enforce_os_updates` | `root_access` | T2 | Planned | Force OS updates within N days. Block deferral beyond threshold. |
| `set_secure_boot` | `root_access` | T2 | Planned | Require UEFI Secure Boot enabled. |

### 4. Data & privacy

| Command | Permission | Tier | Status | Description |
|---------|-----------|------|--------|-------------|
| `set_clipboard_policy` | `root_access` | T2 | Planned | Disable clipboard sharing between apps. |
| `disable_screenshots` | `root_access` | T2 | Planned | Prevent screenshots/screen recording. |
| `disable_camera` | `root_access` | T2 | Planned | Disable camera (prevent photo of card data). |

### 5. Device lifecycle & power

| Command | Permission | Tier | Status | Description |
|---------|-----------|------|--------|-------------|
| `set_auto_lock` | `command_execution` | T1 | Planned | Screen off after N minutes, require auth to wake. |
| `set_power_policy` | `root_access` | T2 | Planned | Disable sleep/hibernate on POS (always-on). |
| `schedule_reboot` | `root_access` | T2 | Planned | Reboot device at a specific time (e.g., 3 AM daily). |
| `set_battery_alert` | `command_execution` | T1 | Planned | Alert when battery drops below N%. Configure low-battery action. |

### 6. Compliance & reporting

| Command | Permission | Tier | Status | Description |
|---------|-----------|------|--------|-------------|
| `run_compliance_scan` | `command_execution` | T1 | Planned | Periodic check: encryption, AV, OS version, app policy. Report non-compliance. |
| `enforce_policies` | `root_access` | T2 | Planned | Re-apply all persisted policies on a schedule. |

## Implementation pattern

Each policy follows the same pattern as existing commands:

1. **Add command type** to `COMMAND_TYPES` in `command_poller.py`.
2. **Add permission** to `REQUIRED_PERMISSION`.
3. **Implement handler** `_run_<policy>()` in `command_poller.py`.
4. **Add dispatch branch** in `_process_command_impl`.
5. **Add describe entry** in `_describe_executed_command`.
6. **Add to AI registry** in `ai/actions.py` `ACTION_REGISTRY` (T1 for read-only, T2 for reversible).
7. **Add to compose templates** in `backend/src/homepot/app/ai_ops/compose_templates.py` and `frontend/src/pages/Device/PushReview.jsx`.
8. **Add tests** in `test_ai_delegation_phase1.py` (expected set + risk tier).
9. **Document** in `docs/` (dedicated doc + update this file).

## AI integration

MDM policies are highly AI-delegatable. Examples:

- "Block social media apps on all POS terminals in Site A"
- "Enable screen lock on all kiosk devices"
- "Ensure encryption is enabled on all devices"
- "Schedule daily reboot at 3 AM for all POS terminals"
- "Check battery levels on all battery-powered POS devices"

The AI can propose these based on anomaly detection, compliance checks, or
technician requests. All policies are T2 (reversible) so they can be rolled
back if needed.

## Policy persistence

Policies are persisted to `C:\ProgramData\Homepot\` (Windows) so they survive
reboots:

| Policy | File |
|--------|------|
| App policy | `app_policy.json` |
| (future) Wi-Fi policy | `wifi_policy.json` |
| (future) Screen lock policy | `screen_lock_policy.json` |
| (future) Battery alert policy | `battery_alert_policy.json` |

## Periodic enforcement

By default, policies are applied once when the command runs. For policies to
survive reboots and catch drift, the agent should:

1. Read persisted policy files on startup.
2. Re-apply all policies on a configurable schedule (e.g., every 6 hours).
3. Report violations (e.g., blocked app found running) to the backend.

This can be implemented as a background task in the agent's main loop, similar
to the heartbeat and telemetry loops.

## Related

- [Set App Policy](set-app-policy.md) — app blacklisting/allowlisting (implemented)
- [Collect Support Bundle](collect-support-bundle.md) — includes policy files in bundle
- [Adding a Device Command](adding-a-device-command.md) — how to add new commands
- [Agent Permissions & Trust Model](agent-permissions-trust-model.md) — permission mapping
- [Real Device Agent](real-device-agent.md) — agent architecture
