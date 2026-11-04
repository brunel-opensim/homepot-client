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
- [ ] LLM provider is Ollama (local) for this run, so no device data leaves
      the host. Confirm via `GET /api/v1/ai/provider`.
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

## After the soak test

Once the success criteria are met, proceed to **Phase 3: background execution
runner** (see `docs/ai-delegation-plan.md` §17.4). The runner auto-executes
approved plans whose autonomy level permits it, removing the manual Execute
click and enabling true "delegate and forget" operation.
PYEOF
echo written