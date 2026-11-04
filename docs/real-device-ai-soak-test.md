# AI delegation soak test — Brunel Device 001

This document is the runbook for the first real-device validation of the AI
delegation stack. It targets one enrolled device so we can accumulate real
`AIActionOutcome` rows, exercise retry/rollback on real latency, and earn the
first autonomy levels without risking a fleet.

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

## Soak sequence (run over 1–2 weeks)

Run each scenario at least 5 times, spacing runs so the reconcile loop
(10 s) and retry backoff (30 s / 60 s) are exercised. Record results in
the table at the bottom.

### S1 — Read-only proposal (health_check)

1. Ask the AI: "Check the health of Brunel Device 001."
2. Expect a proposal with `health_check` (T1, no approval required).
3. Approve the plan, then Execute.
4. Verify the plan reaches `succeeded` with `outcome.verified = true`.
5. Confirm `/api/v1/ai/reliability` shows a `health_check` row.

### S2 — Reversible config change (update_config)

1. Ask: "Set brightness to 30 on Brunel Device 001."
2. Expect a proposal with `update_config` (T2).
3. Approve, Execute, verify the device brightness actually changes.
4. Confirm rollback snapshot captured (`rollback_params` present on the step).

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

### S7 — Fleet proposal

1. Ask: "Run a health check on all devices at Brunel Site."
2. Expect one `health_check` proposal per active device (via
   `propose_fleet_action`).
3. Approve and execute; verify each step is tracked independently.

## Success criteria (before moving to Phase 2)

- [ ] At least 20 completed plans with `outcome.verified = true` across
      `health_check` and `update_config`.
- [ ] At least 1 successful rollback drill (S3).
- [ ] At least 1 retry observed end-to-end (S4).
- [ ] No plan left stuck in `executing` beyond one reconcile cycle (10 s).
- [ ] `/api/v1/ai/autonomy` shows `health_check` at Level 1 or above.
- [ ] `/api/v1/ai/calibration` returns non-empty bands.

## Recording template

| Run | Scenario | Plan ID | Device | Start | End | Status | Outcome verified | Notes |
|-----|----------|---------|--------|-------|-----|--------|------------------|-------|
| 1 | S1 | | Brunel Device 001 | | | | | |
| 2 | S2 | | Brunel Device 001 | | | | | |
| 3 | S3 | | Brunel Device 001 | | | | | |

## After the soak test

Once the success criteria are met, proceed to **Phase 2: agent loop closure**
(see `docs/ai-delegation-plan.md` §17.4 item 6 and the roadmap in the
delegation discussion). The agent will use `get_action_plan_status` to check
its own proposals and report verified results back to the technician without
a manual Execute click.
PYEOF
echo written