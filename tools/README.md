# Tools

Manual command-line tools for device management and soak testing. These are
run by an operator on a workstation/laptop — they are **not** unit tests and
are **never** executed by CI (pytest is scoped to `backend/tests/`).

| Script | Purpose |
|--------|---------|
| `compose-soak-test.py` | Sends each compose command to a device via the command API, verifies the device executed it and that the server recorded it, and reports pass/fail per command. |
| `ai-soak-test.py` | *(planned)* AI-delegation soak test (propose → approve → execute → verify). |

## compose-soak-test.py

Automates the loop an operator otherwise runs by hand: send the command from
Compose Command, wait for it to execute, read the device's Live Logs, then
confirm the command and result in Push History. Each of those steps becomes an
assertion:

| Column | Meaning |
|--------|---------|
| `accept` | the API queued the command (`command_id` returned) |
| `deliv` | `sent_at` is set, so the device polled and acknowledged it |
| `exec` | `executed_at` is set and the status is terminal |
| `hist` | Push History lists the command with the same status polling saw |
| `audit` | `command_queued` → `command_sent` → `command_completed` in the audit log |
| `err` | how many *new* Live Logs rows appeared inside the command's window |
| `elapsed` | seconds from queue to terminal status |

Outcomes are `PASS`, `PASS_NOTE` (executed, but with a failed sub-test verdict
or new log rows), `FAIL`, `BLOCKED` (rejected before it was stored — typically
a missing device grant), `TIMEOUT`, and `SKIPPED`.

A failing command never stops the run. All commands are exercised, then the
report ends with a **Commands that need a look** section listing the command
ids, which checks failed, the agent's result, and the Live Logs time window to
compare against. The only early exit is when the device stops polling after
`restart_agent`; the remaining commands are then marked `SKIPPED` and the
report is still printed.

Before sending anything the script reads the device and prints its lifecycle
state, last-seen time and granted permissions, aborting when a command would be
rejected (pass `--force` to run anyway).

### Usage

```bash
export HOMEPOT_PASSWORD='...'      # avoids the password landing in shell history
python tools/compose-soak-test.py \
    --base-url https://homepot.cabera.com/api/v1 \
    --email maziar.ghorbani@brunel.ac.uk \
    --device-id DEVICE-HSZK-T24Y-TSCX

# Preview the command list without sending anything:
python tools/compose-soak-test.py --list
```

Evidence for every command (checks, timings, results, new log rows) is written
to `compose-soak-results.json` (`--output` to change it).

### Excluded commands

`restart`, `shutdown`, `lock_screen`, `update_app`, `rollback_app`,
`upgrade_all_programs` and `disk_cleanup` are excluded so the device stays
logged in (no PIN entry) and the operator's files are left alone.

### Side effects on the operator's machine

- `update_config` leaves the volume at 50 and the brightness at 75.
- `notify_user` pops a modal on screen.
- `start_program`/`stop_program` open and close Notepad. The stop step targets
  the pid returned by the start step, so a Notepad window the operator already
  had open is never touched.

## Filenames

Use hyphens, not underscores, to match the repo convention (e.g.
`compose-soak-test.py`, not `compose_soak_test.py`). These are standalone
scripts run directly (`python tools/compose-soak-test.py`), never imported as
modules.
