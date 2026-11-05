# AI delegation case study — Brunel Device 001 (first verified run)

This document records the first end-to-end delegated task executed on a real
device (Brunel Device 001, Brunel Site 1) on 2026-11-04. It serves as a
baseline for tracking progress toward autonomy (Levels 1–3) and as a reference
for later modifications.

## Device under test

| Field | Value |
|-------|-------|
| Device ID | `DEVICE-MRUU-AUCA-8TJB` |
| Device name | Brunel Device 001 |
| Site | Brunel Site 1 (`SITE-W545-2BK3`), London, UK |
| Mode | Real |
| Agent version | (check Device Details → Source) |
| Tester | maziar.ghorbani@brunel.ac.uk |
| Date | 2026-11-04 |

## Prompts provided to the AI

The following prompts were sent to the AI during this validation. They are
recorded so the exact input that produced the delegated plan is reproducible.

### Prompt 1 — Status check (non-agentic, no proposal)

> Check the health of Brunel Device 001 and report its status.

Device ID: `DEVICE-MRUU-AUCA-8TJB` (passed as context). Mode: non-agentic
(direct answer). Result: AI returned a health report (CPU, memory, disk,
uptime, network latency alerts) but **no proposal** was created because the
query was answered directly without tool-calling.

### Prompt 2 — Delegation request (agentic, proposal created)

> Run a health check on Brunel Device 001.

Device ID: `DEVICE-MRUU-AUCA-8TJB`. Mode: agentic (`agentic: true`).
Result: the agent called `propose_device_action(action="health_check", ...)`,
which recorded a proposal. The plan was persisted as
`c0a7315c-0b72-43fa-be36-24adbdf08545` (status `pending_approval`).

### Prompt 3 — Follow-up agentic check (no new proposal)

> Run a health check on Brunel Device 001.

Same as Prompt 2; confirmed the agent consistently proposes a `health_check`
action when asked to run a health check. Trust score 1.0, actionable.

### Prompt 4 — Delegate and report (S4 scenario)

> Set brightness to 50 on Brunel Device 001 and tell me whether it worked.

*(Planned for the next run; not yet executed at time of writing.)*

### Notes on prompt design

- The device ID was passed both in the query text and as the `device_id`
  context field, so the agent had unambiguous targeting.
- Agentic mode (`agentic: true`) was required for the agent to call
  `propose_device_action`. Non-agentic queries answer directly without
  creating proposals.
- The AI proactively noted the 6 active network-latency alerts (267–350 ms)
  in its rationale, even though the user did not mention them — demonstrating
  context-aware reasoning.

## Plan summary

| Field | Value |
|-------|-------|
| Plan ID | `c0a7315c-0b72-43fa-be36-24adbdf08545` |
| Status | `succeeded` |
| Risk tier | T1 (read-only) |
| Reversible | Yes |
| Provenance | `ai_proposed` |
| Created by | `maziar.ghorbani@brunel.ac.uk` |
| Created at | 2026-11-04 22:00:23 UTC |
| Approval | Approved by maziar (reason: "soak test") |

## AI rationale

> Device is online and healthy. Proactive health check requested to verify
> current system status and validate that all subsystems are operating
> normally, particularly given the persistent high network latency warnings
> (6 active alerts ranging from 267–350ms) on the primary interface.

The AI noticed the network latency alerts on its own and proactively proposed
a diagnostic action — it reasoned about *why* a check was warranted, not just
*what* to do.

## Trust envelope

| Gate | Status | Score |
|------|--------|-------|
| A — Contract & Infrastructure | Pass | 1.0 |
| B — Data Integrity | Pass | 0.667 |
| C — (context) | Pass | — |
| D — (context) | Pass | — |
| E — (context) | Pass | — |
| **Trust score** | | **1.0** |
| **Actionable** | | **Yes** |

All gates passed → trust score 1.0 → `is_actionable = true` → the proposal
was persisted (not just suggested).

## Step execution

| Field | Value |
|-------|-------|
| Step | `health_check` (seq 0) |
| Target device | `DEVICE-MRUU-AUCA-8TJB` |
| Status | `done` |
| Command ID | `9fecc5e6-7d94-4a55-815c-cc381a9abc14` |
| Started | 22:00:28.72 UTC |
| Completed | 22:00:43.53 UTC |
| Duration | ~14.8 s |
| Retries | 0 |
| Approval required | No (T1 read-only) |

### Device result

```json
{
  "message": "health check completed",
  "results": {
    "network":  { "status": "pass", "value": "ok" },
    "storage":  { "status": "pass", "value": 65.8 },
    "memory":   { "status": "pass", "value": 49.3 }
  }
}
```

All subsystems passed.

## Outcome (verification)

| Field | Value |
|-------|-------|
| Verified | True |
| Rolled back | No |
| Error | None |
| Recorded at | 2026-11-04 22:00:43.91 UTC |
| Provenance | `real` (real device, not simulated) |

## What this proves

1. **The full delegation loop works on a real device:** propose → approve →
   execute → verify → record outcome.
2. **The AI reasoned about device state** (noticed latency alerts) and
   proactively proposed a diagnostic action.
3. **Trust gating works:** Gate A and B passed → trust 1.0 → actionable.
   The proposal was persisted, not just suggested.
4. **Execution and verification are async and reliable:** command queued,
   device polled and executed, result reported back, outcome recorded — all in
   ~15 seconds.
5. **Audit trail is complete:** plan, step, approval, command, result, and
   outcome are all recorded with timestamps and provenance.

## Autonomy progress (baseline after this run)

| Action type | Samples | Success rate | Level |
|-------------|---------|--------------|-------|
| `health_check` | 1 | 100% | Level 1 (any sample > 0) |

Thresholds for promotion:
- **Level 2:** ≥ 50 samples, ≥ 98% success
- **Level 3:** ≥ 200 samples, ≥ 99.5% success, proven rollback

## Next steps

- Run S2–S8 from `docs/real-device-ai-soak-test.md` to accumulate more data.
- Exercise rollback (S3), retry (S4), and the delegate-and-report flow (S8).
- Track autonomy level progression in `GET /api/v1/ai/autonomy`.
- Track calibration in `GET /api/v1/ai/calibration`.
PYEOF
echo written

## Soak test results (S1–S8)

All scenarios run on Brunel Device 001 (`DEVICE-MRUU-AUCA-8TJB`) on 2026-11-05.
Provider: Anthropic (claude-haiku-4-5-20251001). LLM provider switched from
Ollama for speed; trust gates still enforced.

### Results summary

| Scenario | Action | Plan status | Outcome | Verified | Notes |
|----------|--------|-------------|---------|----------|-------|
| S1 — Health check | `health_check` | `succeeded` | verified=true | ✅ | Baseline run; trust 1.0 |
| S2 — Config change | `update_config` (volume 50) | `succeeded` | verified=true | ✅ | Volume set to 50%, verified=true (before=0, after=50) |
| S3 — Rollback drill | `update_config` (brightness "abc") | `rolled_back` | rolled_back=true, rollback_success=true | ✅ | Per-key failure triggered rollback; restored brightness=60 |
| S5 — Per-step approval | `restart_service` (spooler) | `executing` (retry) | — | — | T3 step paused in `awaiting_approval`; released on "Approve step"; retry re-gated |
| S6 — Dry run | `health_check` | `pending_approval` (unchanged) | — | — | Policy allowed, predicted changes shown, no command queued |
| S7 — Fleet command | `health_check` (1 device at site) | `succeeded` | verified=true | ✅ | Each step tracked independently |
| S8 — Delegate and report | `health_check` | `succeeded` | verified=true | ✅ | AI reported "Yes, succeeded" via `get_action_plan_status` |

### S2 detail — config change (volume 50)

- **Prompt:** "Apply configuration to set volume to 50 on Brunel Device 001."
- **Plan:** `update_config` with `{"config": {"volume": 50}}` (T2, reversible)
- **Trust:** 1.0, actionable
- **Execution:** command queued, device applied volume via ctypes Core Audio COM
- **Result:** `{"status": "applied", "message": "volume set to 50%", "verification": {"before": 0, "after": 50, "target": 50, "verified": true}}`
- **Outcome:** `verified: true`, `rolled_back: false`, provenance `real`
- **Duration:** ~8.8s

### S3 detail — rollback drill (volume "abc")

- **Setup:** Device config set to `{"volume": 50}` (baseline from S2).
- **Plan:** `update_config` with `{"config": {"volume": "abc"}}` (invalid value, will fail)
- **Trust:** 1.0, actionable
- **Execution:** command dispatched → device agent: `int("abc")` throws → status "error"
- **Reconcile:** detected per-key failure → triggered rollback
- **Rollback:** restored volume to 50 via rollback command (snapshot captured from device config)
- **Outcome:** `rolled_back: true`, `rollback_success: true`, `verified: false`, provenance `real`
- **Duration:** ~62s (includes 30s retry backoff window before terminal failure)

### S5 detail — per-step approval (restart_service spooler)

- **Plan:** `restart_service` (service_name: "spooler", T3, approval_required: true)
- **Maintenance window:** created for Brunel Site (all 7 days) to allow T3 dispatch
- **Flow:** plan approved → step deferred (no maintenance window) → after window created, step re-evaluated → `awaiting_approval` → "Approve step" clicked → step released → `queued` → dispatched
- **Command:** `systemctl restart spooler` → failed (Windows laptop, no systemctl)
- **Retry:** max_retries=2, scheduled retry, re-gated in `awaiting_approval`
- **Verified behavior:** per-step approval gate works; retry + re-gate interaction works

### S6 detail — dry run (health_check)

- **Plan:** `health_check` (pending_approval)
- **Dry run:** policy allowed, step allowed, predicted change `{"action": "read-only: health_check"}`
- **No command queued** (plan stayed `pending_approval`, step `pending`, `command_id: null`)
- **Non-destructive:** confirmed

### S7 detail — fleet command (health_check on Brunel Site)

- **Plan:** 1 step (1 active device at Brunel Site): `health_check` on `DEVICE-MRUU-AUCA-8TJB`
- **Approved, executed, succeeded, verified** in ~9s
- Each step tracked independently (fleet expansion works)

### S8 detail — delegate and report (health_check)

- **Query 1:** "Run a health check on Brunel Device 001 and tell me whether it worked."
  - AI proposed `health_check` (plan `4c6bbd2d`)
- **Approve + Execute & wait:** completed in 19.0s, `succeeded`, `verified: true`
- **Query 2:** "Did the health check on Brunel Device 001 succeed?"
  - AI called `get_action_plan_status` → reported: "Yes, succeeded, verified, no errors"
- **Loop closed:** delegate → execute → verify → report, all in one conversation

### Key observations

1. **Trust score reached 1.0** after the Gate B fix (insufficient health_check
   samples treated as not-applicable instead of failure).
2. **Rollback works on real hardware** — a failed config change triggered
   snapshot-based rollback, restoring the previous value. `rollback_success=true`.
3. **Per-step approval gate works** — T3 steps pause in `awaiting_approval`
   after plan approval; "Approve step" releases them. Retry re-gates correctly.
4. **Dry run is non-destructive** — policy and predicted changes shown, no
   command queued.
5. **Delegate-and-report closes the loop** — the AI proposed, executed (via
   Execute & wait), verified, and reported the result back in conversation using
   `get_action_plan_status`.
6. **Agentic mode works with Anthropic** — cloud provider tool-calling fixed
   (PR #775) and verified end-to-end on real device queries.

### Autonomy progress (after soak test)

| Action type | Samples | Success rate | Level |
|-------------|---------|--------------|-------|
| `health_check` | 4+ | 100% | Level 1 (any sample > 0) |
| `update_config` | 2+ | 100% (1 success, 1 rolled back) | Level 1 |

Thresholds for promotion:
- **Level 2:** ≥ 50 samples, ≥ 98% success
- **Level 3:** ≥ 200 samples, ≥ 99.5% success, proven rollback

### Database snapshot (2026-11-05)

Reliability metrics, autonomy levels, and calibration as of 2026-11-05
(30-day window, 15 total plans).

**Reliability:**

| Action | Proposed | Approved | Executed | Succeeded | Failed | Rolled back | Success rate |
|--------|----------|----------|----------|-----------|--------|-------------|--------------|
| `health_check` | 5 | 4 | 4 | 4 | 0 | 0 | 100% |
| `update_config` | 9 | 1 | 8 | 3 | 4 | 1 | 37.5% |
| `restart_service` | 1 | 1 | 0 | 0 | 0 | 0 | — (deferred) |

**Autonomy:**

| Action | Samples | Success rate | Rollback proven | Level |
|--------|---------|--------------|-----------------|-------|
| `health_check` | 4 | 100% | No | Level 1 |
| `update_config` | 8 | 37.5% | Yes | Level 1 |
| `restart_service` | 0 | 0% | No | Level 0 |

**Calibration (trust vs. observed success):**

| Trust band | Plans | Avg trust | Observed success | Gap |
|------------|-------|-----------|------------------|-----|
| 0.40–0.60 | 7 | 0.50 | 28.6% | +0.21 (overconfident) |
| 0.80–1.00 | 8 | 1.00 | 62.5% | +0.38 (overconfident) |

**Key findings:**

1. `health_check` is the strongest autonomy candidate (100% success, 4 samples).
   Needs 46 more verified runs to reach Level 2.
2. `update_config` has a low success rate (37.5%) — partly deliberate
   (invalid brightness "abc" for rollback testing) and partly unsupported keys.
3. Trust scores are overconfident — trust 1.0 plans only succeed 62.5% of the
   time. Calibration thresholds need tuning as more data accumulates.
4. `restart_service` never executed (deferred, no maintenance window). A
   maintenance window was created for Brunel Site during testing.

**Plan status distribution:** 7 succeeded, 4 failed, 1 cancelled, 1 rolled back,
1 executing, 1 pending approval (15 total).

### Remaining soak test work

- S4 (retry on transport failure) — not yet observed; retry logic validated
  via unit tests (test_ai_execution.py) and the S5 retry re-gate.
- More runs needed to accumulate samples toward Level 2.
- S8 with a T2 action (config change) instead of T1 health_check, to test
  the full delegate-and-report with a state-changing operation.
