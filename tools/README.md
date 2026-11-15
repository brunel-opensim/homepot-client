# Tools

Manual command-line tools for device management and soak testing. These are
run by an operator on a workstation/laptop — they are **not** unit tests and
are **never** executed by CI (pytest is scoped to `backend/tests/`).

| Script | Purpose |
|--------|---------|
| `compose-soak-test.py` | Sends each compose command to a device via the command API, verifies the device executed it and that the server recorded it, and reports pass/fail per command. |
| `ai-soak-test.py` | Delegates each compose command to the AI in natural language and verifies the AI proposed the right action, the plan was approved and executed, and the device result was verified. |

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
| `err` | how many *real* device errors appeared inside the command's window |
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
to a timestamped file under `soak-runs/` (a git-ignored directory), e.g.
`soak-runs/compose-soak-results-20261115T153000Z.json`. Pass `--output` to send
it somewhere else. The report also prints the exact path when it finishes.

### Excluded commands

`restart`, `shutdown`, `lock_screen`, `update_app`, `rollback_app`,
`upgrade_all_programs` and `disk_cleanup` are excluded so the device stays
logged in (no PIN entry) and the operator's files are left alone.

### Side effects on the operator's machine

- `update_config` leaves the volume at 50 and the brightness at 75.
- `notify_user` pops a modal on screen.
- `start_program`/`stop_program` spawn and kill a `ping.exe` that runs for a few
  minutes. The stop step targets the pid returned by the start step, so a window
  the operator already has open is never touched.

## ai-soak-test.py

Drives the AI delegation loop instead of the command API: ask the AI in natural
language, then prove the loop completed. It exercises the **same 24 commands in
the same order** as `compose-soak-test.py`, so the two runs are directly
comparable (same coverage, one composed, one delegated).

| Column | Meaning |
|--------|---------|
| `prop` | `POST /ai/query` returned a proposal (not a direct answer) |
| `match` | the proposal's action set contains the expected action |
| `plan` | a `plan_id` was returned, so the plan was persisted |
| `approv` | the plan reached `approved` (or was auto-approved by autonomy) |
| `exec` | the plan reached a terminal status within the per-command budget |
| `verif` | terminal status is `succeeded` and `outcome.verified` is set |
| `hist` | Push History lists the command the plan dispatched |
| `audit` | `command_sent` → `command_completed` in the audit log (the AI executor does not emit `command_queued`; that is recorded separately as evidence of the gap) |
| `err` | how many *real* device errors appeared inside the command's window |
| `elapsed` | seconds from the AI query to the terminal plan status |

Outcomes are the same set as the compose soak (`PASS`, `PASS_NOTE`, `FAIL`,
`BLOCKED`, `TIMEOUT`, `SKIPPED`), with two AI-specific meanings for `BLOCKED`:
the validation envelope was not actionable (a gate failed), or the plan was
blocked by policy / rejected.

### What it checks that the compose soak cannot

- **The AI actually proposes the expected action.** A query that answers
  directly, or proposes the wrong action (e.g. `run_command` instead of
  `start_program`), is a `FAIL` with the proposed actions recorded. This is the
  point of the run: it finds delegation gaps, not just transport failures.
- **Per-step approval.** T3 actions (`restart_agent`, `restart_service`,
  `run_command`, `run_script`) get their own gate after plan approval. The
  script releases each gated step before executing.

### Usage

```bash
export HOMEPOT_PASSWORD='...'
python tools/ai-soak-test.py \
    --base-url https://homepot.cabera.com/api/v1 \
    --email maziar.ghorbani@brunel.ac.uk \
    --device-id DEVICE-HSZK-T24Y-TSCX \
    --provider anthropic

# Preview the delegated list without sending anything:
python tools/ai-soak-test.py --list
```

Prompts reference the device by `device_id` (not its display name) so the AI
does not have to resolve a name through `find_device` first. Name resolution is
a separate capability and is out of scope here.

### Provider

`--provider` (`ollama` / `openai` / `anthropic`) pins the run to one LLM
provider: the server is switched via `PUT /api/v1/ai/provider` first (admin
only), and the provider + model are recorded in the evidence bundle. Omit it to
run against whatever provider is already active. Each command also records the
`provider` from its own `/ai/query` response, plus a truncated copy of the AI's
`response` and its `tools_called` list, so a "no proposal" failure is
diagnosable after the fact.

### Registry awareness

The AI can only propose an action that is declared in `ACTION_REGISTRY`
(`ai/actions.py`); the Compose Command page reads `COMPOSE_TEMPLATES`
(`backend/src/homepot/app/ai_ops/compose_templates.py`). The two are kept in
sync by `test_compose_templates_and_registry_stay_in_sync` in
`backend/tests/test_ai_delegation_phase1.py`, which fails if a template or
registry entry is added without the other. Two entries are intentionally
asymmetric: `bootstrap_winget` (Compose-only, technician utility) and
`rollback_config` (registry-only alias for `update_config`).

## Notes learned from real runs

- **`/error-logs` is not an error-only log.** It returns the whole device log
  stream: the periodic `Status report: ONLINE ...` heartbeat
  (`category="status"`) and each command's own `Command completed: ...` line
  (`category="command"`), both at `severity="info"`. The first run's error check
  counted those and marked all 24 commands as notes. The `err` column now
  ignores `status`/`command` categories and anything below warning severity.
  A 300-row sample from a full run was 276 heartbeats plus 24 command lines and
  zero errors.
- **`last_seen` alone cannot prove an agent restart.** It advances while a
  command sits queued, and a *failed* restart leaves the old process
  heartbeating. The probe therefore waits for the restart counter to go up
  (`agent_restart_count`) or the reported uptime to drop (`agent_uptime_seconds`
  back to a few seconds), and reports "unverified" rather than guessing when
  neither is available.
- **`start_program` + `stop_program` cannot use Notepad on Windows 11.** Notepad
  is a packaged app: `notepad.exe` hands off to the Store process and exits, so
  the returned pid is already gone and the stop step reports `killed: 0`
  ("process not running"). The soak test uses `ping.exe` instead so the kill
  path is actually exercised.
- **Device clocks drift.** A run reported the device's `executed_at` 5-6s ahead
  of the workstation. Timing deltas are clamped at zero and clock skew is
  reported as a note instead of a negative duration.

## Code quality

These tools are not covered by CI (pytest is scoped to `backend/tests/` and
mypy to `backend/src/homepot/`), so run the checks by hand before changing
them. They are not busywork: the first soak run shipped two measurement bugs —
counting its own completion lines as "new errors", and treating `last_seen` as
proof of an agent restart — that passed `black`/`isort`/`flake8`/`mypy` and
were only caught by the complexity check and the test suite below.

Run all of these from the repo root before opening a PR that touches `tools/`:

```bash
# Format + lint. black/isort/flake8 also run in the pre-commit hook.
.venv/bin/black --check tools/
.venv/bin/isort --check-only tools/
.venv/bin/flake8 tools/

# Type-check the scripts. The test files are untyped pytest, like
# backend/tests/, so they are outside the mypy gate.
.venv/bin/mypy --config-file=backend/mypy.ini \
    tools/compose-soak-test.py tools/ai-soak-test.py

# Stricter than CI: keep every function at McCabe <= 10. A big run_one() was
# the reason the two bugs hid in plain sight.
.venv/bin/flake8 --max-complexity=10 \
    tools/compose-soak-test.py tools/ai-soak-test.py

# Security lint. CI's flake8-bandit ignores S105 (hardcoded passwords), so run
# bandit standalone too; the single B105 on OUTCOME_PASS is silenced with
# `# nosec B105` because it is a status label, not a credential.
.venv/bin/bandit -q tools/compose-soak-test.py tools/ai-soak-test.py

# Hermetic test suites — fake devices and APIs, no network, never touch real
# hardware or the LLM. These prove the log filter, the restart probe, and the
# AI proposal/outcome classification behave.
.venv/bin/python -m pytest tools/test_compose_soak_test.py \
    tools/test_ai_soak_test.py -n 0 -p no:cacheprovider --no-cov -q
```

`black`/`isort` will rewrite in place if you drop `--check`; everything else is
read-only.

## Filenames

Use hyphens, not underscores, to match the repo convention (e.g.
`compose-soak-test.py`, not `compose_soak_test.py`). These are standalone
scripts run directly (`python tools/compose-soak-test.py`), never imported as
modules. The one exception is the test file: pytest only collects `test_*.py`,
so it is `test_compose_soak_test.py` to match `backend/tests/`.
