# Two-device demonstration queries

Use these four copy/paste prompts for a demonstration with two devices that
enrol during the session. The device target is deliberately left as a
placeholder: replace `<DEVICE_1_ID_OR_NAME>` and `<DEVICE_2_ID_OR_NAME>` with
the business ID or exact display name from the Devices page once each device
has enrolled.

All four prompts create a proposal only. Nothing executes until a technician
reviews and approves the plan in the Dashboard.

## Prerequisites

- Both devices have enrolled and appear on the Devices page.
- **Monitor access** is granted on both devices. This covers
  `command_execution`, `process_monitoring`, and `network_monitoring`.
- **Manage access** is granted on a device only for the manage prompt. This
  adds `root_access`. The User App allows manage access only when monitor
  access is already on.
- The AI provider is healthy. No provider switch is required for these prompts.

See [Agent permissions and trust model](agent-permissions-trust-model.md#user-app-presentation-owner-facing)
for the owner-facing grant definitions.

## Device A prompts

| Access tier | Copy/paste query | Expected proposal | Permission exercised |
|---|---|---|---|
| Monitor | `Run a health check on <DEVICE_1_ID_OR_NAME> and report whether it passed.` | `health_check` | `command_execution` (Monitor) |
| Manage | `Apply configuration to set volume to 50 and brightness to 75 on <DEVICE_1_ID_OR_NAME>.` | `update_config` with `config.volume=50` and `config.brightness=75` | `root_access` (Manage) |

## Device B prompts

| Access tier | Copy/paste query | Expected proposal | Permission exercised |
|---|---|---|---|
| Monitor | `List processes on <DEVICE_2_ID_OR_NAME>.` | `list_processes` | `process_monitoring` (Monitor) |
| Manage | `Apply configuration to set volume to 60 and brightness to 40 on <DEVICE_2_ID_OR_NAME>.` | `update_config` with `config.volume=60` and `config.brightness=40` | `root_access` (Manage) |

## Presentation notes

- Run the monitor prompt first on each device. It should produce a proposal
  even with manage access turned off.
- Turn on manage access only when ready for the manage prompt, then run it on
  the same device. The `update_config` proposal is a small, reversible config
  change suitable for a demo.
- If the AI cannot resolve a placeholder after enrolment, replace it with the
  device's business ID, for example `DEVICE-HSZK-T24Y-TSCX`.
- The AI consults the registry-backed Compose Command templates before
  proposing, so the manage prompts use the `APPLY_CONFIG` template rather than
  an invented shell command.
- Do not approve a proposal unless the demo intends to run that command.
