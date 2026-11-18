# AI delegation soak test — Brunel Device 001

This document is the runbook for a **fast (1–2 day)** real-device validation of
the AI delegation stack on a single device. The goal is to prove that the AI
can be **delegated a task, execute the underlying device command, verify the
result, and report success back** — without a human clicking Execute.

Device under test: **Brunel Device 001** at site **Brunel Site**.

## Preconditions

- [ ] Device enrolled, online, agent reporting a version (not "REAL") in
      Device Details → Source.
- [ ] Technician account has operator access to Brunel Site.
- [ ] `connectivity_state` is `online`. The harness aborts before sending
      anything otherwise: proposals are refused for offline devices, so a run
      started then measures nothing. Check the last-seen age too — a device
      that has not polled for hours is not reachable even if `status` still
      says online.
- [ ] LLM provider chosen for the run is recorded in the evidence file. Server
      runs follow the provider matrix order Anthropic → OpenAI → Ollama, so
      they used Anthropic (`claude-haiku-4-5`); use Ollama when device data
      must not leave the host. Confirm via `GET /api/v1/ai/provider` or pass
      `--provider`.
- [ ] `HOMEPOT_AI_STEP_MAX_RETRIES` left at default (2) so retry fires on
      real transport failures.
- [ ] A baseline `Apply Configuration` (volume/brightness) has succeeded on
      the device at least once, so rollback has something to undo.

## Delegated commands (management controls)

The AI can be delegated the following device-management commands. Each becomes
a proposal that is approved, executed, verified, and reported back:

| Command | Action | Tier | What it does |
|---------|--------|------|--------------|
| Check device health | `health_check` | T1 (read-only) | CPU, memory, disk, network, OS info |
| List running processes | `list_processes` | T1 (read-only) | Process list with PIDs |
| Scan filesystem | `scan_filesystem` | T1 (read-only) | Directory listing |
| Apply configuration | `update_config` | T2 (reversible) | Set volume, brightness, log level, etc. |
| Restart device | `restart` | T2 (reversible) | Reboot the device |
| Roll back config | `rollback_config` | T2 (reversible) | Restore previous config |
| Restart a service | `restart_service` | T3 (disruptive) | Restart a named service |
| Fleet health check | `health_check` (via `propose_fleet_action`) | T1 | Same check across a site/fleet |

The technician delegates by asking in natural language, e.g.:
- "Check the health of Brunel Device 001 and tell me if anything is wrong."
- "Set brightness to 30 on Brunel Device 001 and confirm it worked."
- "Restart Brunel Device 001 and report back when it's online again."
- "Run a health check on all devices at Brunel Site."

## Soak sequence (run over 1–2 days)

Run each scenario 2–3 times. Record results in the table at the bottom.

### S1 — Read-only command (health_check)

1. Ask the AI: "Check the health of Brunel Device 001."
2. Expect a proposal with `health_check` (T1, no approval required).
3. Approve the plan, then Execute (or use `execute-and-wait` once available).
4. Verify the plan reaches `succeeded` with `outcome.verified = true`.
5. Confirm the AI reports the health result back to you.

### S2 — Configuration command (update_config)

1. Ask: "Set brightness to 30 on Brunel Device 001."
2. Expect a proposal with `update_config` (T2).
3. Approve, Execute, verify the device brightness actually changes.
4. Confirm the AI reports "brightness set to 30, verified" (or failure).
5. Verify rollback snapshot captured (`rollback_params` present on the step).

### S3 — Rollback drill

1. Trigger S2, then cancel the plan mid-execution (or induce a per-key
   failure by sending an invalid config key).
2. Verify the plan moves to `rolling_back` then `rolled_back`, and the device
   brightness is restored.
3. Confirm `outcome.rolled_back = true` and `rollback_success = true`.

### S4 — Retry on transport failure

1. Disconnect the device (or block its heartbeat) and trigger S2.
2. Verify the step schedules a retry (`retry_count` increments,
   `next_retry_at` set in the future) instead of failing immediately.
3. Reconnect the device before the backoff elapses and confirm re-dispatch.

### S5 — Per-step approval (restart_service)

1. Ask: "Restart the print spooler on Brunel Device 001."
2. Expect a plan with `restart_service` (T3) marked `approval_required`.
3. Approve the plan; the step should pause in `awaiting_approval`.
4. Click "Approve step" in the UI; verify dispatch and completion.

### S6 — Dry run

1. On any pending plan, click "Dry run" and confirm the policy result and
   predicted changes are shown without queueing a command.

### S7 — Fleet command

1. Ask: "Run a health check on all devices at Brunel Site."
2. Expect one `health_check` proposal per active device.
3. Approve and execute; verify each step is tracked independently.

### S8 — Delegate and report (end-to-end)

1. Ask the AI: "Set brightness to 50 on Brunel Device 001 and tell me
   whether it worked."
2. The AI should propose, and once approved and executed, report the verified
   result (success or failure) back in the conversation.
3. This is the core delegation loop: delegate → execute → verify → report.

## Success criteria (end of day 2)

- [ ] At least 5 completed plans with `outcome.verified = true` across
      `health_check` and `update_config`.
- [ ] At least 1 successful rollback drill (S3).
- [ ] At least 1 retry observed end-to-end (S4).
- [ ] No plan left stuck in `executing` beyond one reconcile cycle (10 s).
- [ ] `/api/v1/ai/autonomy` shows `health_check` at Level 1 or above.
- [ ] S8 (delegate and report) works end-to-end at least once.

## Recording template

| Run | Scenario | Plan ID | Device | Start | End | Status | Outcome verified | Notes |
|-----|----------|---------|--------|-------|-----|--------|------------------|-------|
| 1 | S1 | | Brunel Device 001 | | | | | |
| 2 | S2 | | Brunel Device 001 | | | | | |
| 3 | S8 | | Brunel Device 001 | | | | | |

## Findings (first runs)

Five runs of `tools/ai-soak-test.py` against Anthropic (`claude-haiku-4-5`)
recorded 18/24, then 14/24, then 19/24, then 19/24 again, and finally **24/24**.
The second run *degraded*; the third ran against a clean memory store and an
uncontaminated command history, and is the baseline the fixes below are
measured against. Every gap was in the AI's **action selection**, not in the
propose → approve → execute → verify loop.

The harness prints each command's risk tier (T1 read-only, T2 reversible, T3
disruptive) in the preview, evidence table, timings, failure detail and JSON
records. The value comes from `ACTION_REGISTRY`, so the report cannot drift
from the actions the AI is allowed to propose.

The earlier 18/24 and 14/24 runs predate the retained evidence files; the
three most recent runs are:

| Run | Score | Trigger | Evidence |
|-----|-------|---------|----------|
| baseline | 19/24 | clean memory + command history | `ai-soak-results-20261116T125701Z.json` |
| after #1004 | 19/24 | action descriptions deployed, but not delivered | `ai-soak-results-20261116T134459Z.json` |
| after #1006 + #1007 | **24/24** | schema delivery and telemetry provenance fixed | `ai-soak-results-20261117T091430Z.json` |
| after #1010 | 23/24 | prior command history retained, freshness fix not yet deployed | `ai-soak-results-20261117T123719Z.json` |
| after #1011 | 23/24 | stale history labelled; no records removed between runs | `ai-soak-results-20261117T133211Z.json` |
| after #1012 + #1013 | **24/24** | host/port normalized; tier column added; history untouched | `ai-soak-results-20261117T142741Z.json` |

The baseline file came from a run at 2026-11-16 13:10 UTC (788.4 s). Run 5
used `claude-haiku-4-5-20251001` on `DEVICE-HSZK-T24Y-TSCX`, started
2026-11-17 09:28 UTC, and took 850.8 s. All 24 commands proposed the expected
action, reached `succeeded`, verified, appeared in Push History, and had a
matching audit trail. The proposal queue was empty at the end.

The final run after #1012 and #1013 used the same provider, model and device,
started 2026-11-17 14:40 UTC, and took 770.0 s. It also scored **24/24** with
all actions matching, executing, verifying, appearing in Push History and
having matching audit trails. No command records were removed before it; the
new tier column showed 11 T1, 9 T2 and 4 T3 commands.

A sixth attempt was refused before sending anything: the device had not polled
for ~9.6 hours and was `offline`, so every proposal would have been rejected by
the connectivity gate. The harness now blocks that case in preflight (#1008).
Two later runs took 803.4 s and 865.4 s; both scored 23/24 for the same
`network_test` reason described below. The final run took 770.0 s and passed
24/24.

Earlier runs could be contaminated when the AI's `get_command_history` tool
returned the last five command results with no age filter: a command executed
shortly before a soak could be answered from instead of proposing a new one.
Two read-only failures (`list_processes`, `list_connections`) were traced to
exactly this and disappeared on the clean re-run. The context builder now
labels every command with its age, removes result payloads older than 30
minutes, and states in the prompt that command history is historical evidence
rather than a live reading. Runs no longer need database records removed
between attempts; the full audit history can stay in place. The run after
#1011 confirmed this: with all prior command records still in the database,
every command except `network_test` proposed the expected action and passed.

### network_test host/port (fixed in #1012)

The two runs after #1010 both failed only command 6 (`network_test`). The
recorded payload was `host='homepot.cabera.com:443'`: the model appended the
port to the hostname. The device resolves DNS and sends ICMP with `host` as
given, so `getaddrinfo` failed even though the host itself is reachable. The
action description now leads with the rule that `host` is a bare hostname and
the TCP port belongs in the separate `port` param, and
`propose_device_action` splits a single-colon `host:port` value when no
explicit port was supplied. IPv6 literals and explicit ports are unchanged.
The final run recorded `host='homepot.cabera.com'` and `port=443` and passed
command 6.

### Memory pollution (fixed)

Long-term memory recalled the first run's "proposal recorded, pending approval"
answers, so on the second run the model answered "I already proposed X" and
skipped proposing (`list_processes`, `scan_filesystem`, `uninstall_program`,
`notify_user`). Fixed on both sides: proposal answers are no longer written to
long-term memory (`_should_persist_answer_to_memory`), and action requests no
longer auto-recall memory at all (`_should_recall_memory`); see
[docs/ai-memory.md](ai-memory.md).

### Deterministic action-mapping gaps

`run_command_unprivileged` and `run_script` are consistently proposed as the
generic `run_command`. `start_program` showed the same failure in the first
runs, then mapped correctly.

Root cause, in two layers. The first was visible: `allowed_actions_summary()`
— the single source of truth rendered into `propose_device_action`'s docstring
— advertised **bare action names grouped by risk tier**, with no description and
no parameters:

```
'run_command_unprivileged', 'set_service_state', 'start_program',
'update_config' ... (T2 reversible)
'restart_agent', 'run_script', 'run_command' ... (T3 disruptive)
```

The registry carried good descriptions the whole time, so the model had no way
to tell `run_command` from `run_command_unprivileged` or `run_script`, and no
hint that `run_script` takes a `script` parameter while `run_command` takes a
`command`.

The second layer was hidden and is the reason the first fix changed nothing.
Parameter descriptions are not taken from the docstring directly —
`_function_to_tool_schema()` parses it with `docstring_parser` and copies each
parsed parameter description into the JSON schema sent to the model. In
`propose_device_action`'s `Args` block, `target_device_id`'s continuation line
was indented no deeper than the parameter name:

```
    target_device_id: The device identifier the action applies to. If you only
    have a device name, call find_device first to resolve the business ID.
```

The Google-style parser reads that second line as the start of a new parameter
and raises "Expected a colon". The exception was swallowed, `param_descriptions`
became `{}`, and **every parameter description for the tool was dropped** —
including the action list. So the list had never reached the model, in any run,
with or without descriptions.

This was proved by measurement, not inspection: the description fix was
deployed and a full run came back at exactly the same 19/24 with the same five
failures. `list_devices` had the same defect and was also delivering no
parameter descriptions.

Fixed: continuation lines are indented deeper than their parameter name in both
tools, `_function_to_tool_schema()` now logs a warning instead of failing
silently, and `docstring-parser` is pinned in `backend/requirements.txt`
(it was only present as a transitive dependency of `anthropic`, so a deployment
using another provider would have lost every parameter description). Tests now
assert the action list survives into the schema and that no tool ships an
undocumented parameter.

The action list itself also carries a description and required parameters per
action now, e.g. `'run_script' - Run an elevated script on the device.
[params: script]`. That grows the summary from ~640 B to ~3 KB (roughly 580
extra tokens per request).

Status: **Done** — run 5 proposed the expected action for all 24 commands,
including `update_config` (#13), `run_command_unprivileged` (#14) and
`run_script` (#21), each approved, executed and verified.

### Direct-answer gaps

`tail_system_log` and `get_system_info` are answered directly instead of being
proposed as actions. "Read the most recent system log events" and "get the
system information" read as questions, so the model calls a telemetry tool and
stops.

The telemetry tools made that look like the right answer. `get_error_logs`
returns HOMEPOT's own event log — status reports and command events, including
`info`-level rows — and its description said "error logs for a device", so a
table of timestamped events reads exactly like a system log.
`get_device_status` returns identity, OS, firmware and health, which reads
exactly like system information. Neither tool said where its data comes from,
and the system prompt never distinguished a fresh reading from the device from
what the server last recorded.

Fixed in the prompt and the tool descriptions rather than in the soak prompts,
because the ambiguity is real:

- the action verb list in `AGENT_SYSTEM_PROMPT` now includes read, get, fetch,
  gather and inspect, and names "read the device's system log" and "get its
  system or hardware information"
- a new rule states that server telemetry is a summary, not a fresh reading,
  and that asking for data only the device can produce must be proposed
- `get_error_logs` and `get_device_status` say it in their first line — the only
  part of a docstring that reaches the model — and point to the action that
  reads the machine

Status: **Done** — run 5 proposed `tail_system_log` (#5) and `get_system_info`
(#8) as actions instead of answering from telemetry; both executed and
verified.

### `update_config` capability confusion

"Set volume/brightness" is answered with "the toolkit has no action for volume
or brightness", even though `update_config` declares exactly those keys.

Same missing-description root cause, with an extra wrinkle: the useful detail
sat in the *second* sentence of the registry description ("Apply a
configuration change to a device. The 'config' param is a dict ... e.g.
brightness, volume"), so a leading-clause summary would still have hidden it.
The description now opens with what it changes — "Change device settings:
volume, brightness, log_level, or hostname" — and that leading clause is what
the advertised list shows.

Status: **Done** — run 5 delegated the volume/brightness command to
`update_config` and verified the change.

### Audit trail parity

Earlier runs showed `command_sent` + `command_completed` but no
`command_queued` for AI-dispatched commands, so the soak tool recorded
`queued=false` on all 24 rows even in the 24/24 run. The executor and rollback
paths now write the same `command_queued` event as the operator command
endpoint, with the command id, type, payload, plan id and acting technician in
the audit metadata. The soak tool now treats a missing queued event as a
failure instead of a note.

Status: **Done** in code; backend tests cover both dispatch paths and the
post-fix soak is the end-to-end confirmation.

### Historical failed plans and harness cleanup

A triage of `GET /api/v1/ai/action-plans?status=failed` found eight failed
plans, not six. Four are from `DEVICE-MRUU-AUCA-8TJB` and were intentional S3
rollback drills: they used `update_config` with `brightness="abc"` and carried
no rollback snapshot, so a failed step was the expected result. Two more manual
probes on that same device (`restart_service` for `spooler` and `start_program`
for `notepad.exe`) also failed. That device has since been removed, its command
records are gone, and the root cause of those two probes is no longer
recoverable from retained data. None of these six plans came from a final soak
run.

The other two failed plans are the `network_test` runs from 2026-11-17
12:40 UTC and 13:34 UTC on `DEVICE-HSZK-T24Y-TSCX`. Both sent
`host="homepot.cabera.com:443"`; the device tried to resolve the port as part
of the hostname and failed. This is the host/port defect fixed in #1012 and
documented above. The final 24/24 run used separate `host` and `port` fields.

A separate harness gap remains. `tools/ai-soak-test.py::run_one` checks
`action_match` before it reads `plan_id`. When the AI proposes an unexpected
action, the command is recorded as FAIL and the function returns without
approving or executing anything. That is correct for safety, but a proposal
that was already persisted is not rejected and its `plan_id` is not written to
the evidence record. The gap did not create an orphan in the observed runs: the
only action-mismatch failure (`gpt-4o-mini`, 2026-11-17 16:04 UTC, command 15)
produced no proposal, so `plan_id` was `null`. The risk is real for a future
provider that proposes the wrong action but still returns a plan.

The API can reject a plan in `pending_approval` even when its target device has
been removed, so cleanup is safe. Recommended fix: capture `plan_id` before the
action-match check, reject the pending plan with an explicit reason, and record
the rejection in the evidence while keeping the command FAIL. Add a unit test
that asserts the reject call and that no approve or execute call follows.

Status: **Open** for the harness cleanup; the eight historical failed plans
need no further action. Triage evidence is in
`soak-runs/failed-plans-investigation-20261118T082147Z.json` (git-ignored).

## After the soak test

Once the success criteria are met, proceed to **Phase 3: background execution
runner** (see `docs/ai-delegation-plan.md` §17.4). The runner auto-executes
approved plans whose autonomy level permits it, removing the manual Execute
click and enabling true "delegate and forget" operation.
