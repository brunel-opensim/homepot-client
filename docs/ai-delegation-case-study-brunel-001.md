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