# AI-delegatable commands reference

This document lists every device-management command that the AI can be delegated
to execute, grouped by risk tier. It is the master checklist for the soak test
and for the automated soak script (Option B). Reboot (`restart`) and shutdown
(`shutdown`) are excluded from automated testing to avoid disrupting the device.

## T1 — Read-only (no state change, no approval required)

| # | Action | Command type | Params | Description |
|---|--------|-------------|--------|-------------|
| 1 | `health_check` | `health_check` | none | CPU, memory, disk, network diagnostics |
| 2 | `list_processes` | `list_processes` | `max_results`, `sort_by`, `include_memory` | List running processes |
| 3 | `scan_filesystem` | `scan_filesystem` | `path`, `max_depth`, `include_sizes` | Scan filesystem for files |
| 4 | `list_installed_programs` | `list_installed_programs` | none | List installed programs (registry) |
| 5 | `list_connections` | `list_connections` | `filter_state`, `limit` | List active network connections |

## T2 — Reversible (requires approval, can be rolled back)

| # | Action | Command type | Params | Description |
|---|--------|-------------|--------|-------------|
| 6 | `update_config` | `update_config` | `config` (dict of settings) | Apply configuration change |
| 7 | `rollback_config` | `update_config` | `config` (previous values) | Roll back a config change |
| 8 | `start_program` | `start_program` | `path`, `args` | Launch a program |
| 9 | `stop_program` | `stop_program` | `name`, `force` | Stop a running process |
| 10 | `install_program` | `install_program` | `package`, `timeout_seconds` | Install via winget |
| 11 | `uninstall_program` | `uninstall_program` | `package`, `timeout_seconds` | Uninstall via winget |
| 12 | `update_program` | `update_program` | `package`, `timeout_seconds` | Update a single program |
| 13 | `run_command_unprivileged` | `run_command_unprivileged` | `command`, `timeout_seconds` | Run command as user |

## T3 — Disruptive (requires approval + maintenance window, not reversible)

| # | Action | Command type | Params | Description |
|---|--------|-------------|--------|-------------|
| 14 | `restart_service` | `run_command` | `service_name` | Restart a named OS service |
| 15 | `upgrade_all_programs` | `upgrade_all_programs` | `timeout_seconds` | Upgrade all programs via winget |
| 16 | `run_command` | `run_command` | `command`, `timeout_seconds` | Run elevated command |
| 17 | `run_script` | `run_script` | `script`, `timeout_seconds` | Run elevated script |

## Excluded from automated testing

| Action | Reason |
|--------|--------|
| `restart` | Reboots the device — disruptive to soak test |
| `shutdown` | Shuts down the device — disruptive to soak test |

## Fleet variant

All T1/T2/T3 actions can be proposed fleet-wide via `propose_fleet_action(action, site_id, ...)`, which expands into one per-device proposal.

## Testing checklist

For each command, verify:
- [ ] AI proposes the correct action with valid params
- [ ] Plan is approved (plan-level + per-step for T3)
- [ ] Command is dispatched and executed on the device
- [ ] Result is reported back (success or failure)
- [ ] Outcome is recorded (`verified: true` for success)
- [ ] Rollback works (T2 only, if a prior config exists)
- [ ] Retry works on transport failure (T2/T3, transport-level only)

## Manual test sequence (1-2 days)

Run each command once on Brunel Device 001, approve, execute & wait, verify result:

1. `health_check` — "Run a health check on Brunel Device 001."
2. `list_processes` — "List running processes on Brunel Device 001."
3. `scan_filesystem` — "Scan the filesystem of Brunel Device 001."
4. `list_installed_programs` — "List installed programs on Brunel Device 001."
5. `list_connections` — "List network connections on Brunel Device 001."
6. `update_config` — "Apply configuration to set volume to 50 on Brunel Device 001."
7. `run_command_unprivileged` — "Run `ipconfig` on Brunel Device 001."
8. `start_program` — "Start notepad on Brunel Device 001."
9. `stop_program` — "Stop notepad on Brunel Device 001."
10. `restart_service` — "Restart the print spooler on Brunel Device 001." (needs maintenance window)
11. `run_command` — "Run `systeminfo` on Brunel Device 001."
12. `install_program` — "Install Notepad++ on Brunel Device 001." (needs network)
13. `update_program` — "Update Notepad++ on Brunel Device 001."
14. `uninstall_program` — "Uninstall Notepad++ from Brunel Device 001."
15. `upgrade_all_programs` — "Upgrade all programs on Brunel Device 001."
16. `run_script` — "Run a script on Brunel Device 001."

## Automated soak script (Option B)

Once manual testing is complete, create an automated script that:
- Iterates through all T1 and T2 commands (safe ones).
- For each: proposes via AI, approves, executes & waits, verifies result.
- Logs pass/fail per command.
- Runs overnight to accumulate samples across all action types.
- Skips T3 actions (or runs them only with maintenance window).

This ensures we test the full registry, not just health_check.
PYEOF
echo written