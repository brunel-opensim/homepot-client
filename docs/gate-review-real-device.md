# Gate review: real-device observations (Brunel Device 001)

This document captures the step-by-step review of Gates A–E based on real-device
soak-test data from Brunel Device 001 (2026-11-04 to 2026-11-07). It
identifies what is working, what needs tuning, and what should change for
production. It is a discussion document — no code changes.

## Summary of real-device gate results

| Gate | Name | Status on Brunel 001 | Trust impact | Notes |
|------|------|---------------------|--------------|-------|
| A | Contract & Infrastructure | ✅ Pass (score 1.0) | Full credit | Schema conformance + DB readiness both pass |
| B | Data Integrity | ✅ Pass (after fix) | 0.667 partial credit | Continuity/gap checks treated as not-applicable (0 health_check samples) |
| C | Context Readiness | ✅ Pass | Full credit | All required blocks present, context bounded |
| D | Permission & Capability | ✅ Pass | Full credit | Device permissions consistent with capabilities |
| E | Lifecycle Integrity | ✅ Pass | Full credit | Device active, healthy, credentials valid |

**Overall trust score: 1.0** (all gates pass). However, calibration data shows
the *observed* success rate is only 62.5% for plans rated at trust 1.0 — a
significant overconfidence gap.

---

## Gate A — Contract and Infrastructure

### What it checks

1. **Schema conformance** (`A.api_schema_conformance`): Verifies that the ORM-mapped
   columns for `device_metrics` and `health_checks` exist in the live database by
   running a real `SELECT` of each column. Works identically on SQLite and
   PostgreSQL.

2. **DB readiness** (`A.db_readiness`): Confirms core tables are queryable and
   reports row counts for `device_metrics` and `health_checks`.

### Real-device observations

- **Schema conformance: Pass.** All mapped columns exist in production PostgreSQL.
- **DB readiness: Pass.** `device_metrics` has 22,500+ rows; `health_checks` has 0
  rows (the simulated agent manager doesn't poll real devices).
- **Root cause of earlier failure (fixed in PR #776):** `ContextBuilder.get_state_context`
  compared `DeviceStateHistory.device_id` (integer FK) with the string device_id,
  causing `integer = character varying` which aborted the transaction and cascaded
  into Gate A failure (trust 0.00). Fixed by resolving the string to the integer PK.
- **Trust impact:** Full credit (1.0). Gate A is a hard gate — if it fails,
  trust drops to 0 and the AI cannot make any recommendations.

### Recommendations

1. **No threshold changes needed.** Gate A is a binary pass/fail on schema/DB
   availability. It should remain strict.
2. **Consider splitting the health_checks row count** from the DB readiness check.
   Currently, 0 health_check rows doesn't fail Gate A (it reports the count
   informationally). But the gate's message says "are queryable" which is slightly
   misleading when there are 0 rows. Consider changing the message to
   "queryable (N rows)" for clarity.
3. **Add a check for the `ai_action_plan` / `ai_action_step` tables** in schema
   conformance, since the AI delegation stack now depends on them. Currently only
   `device_metrics` and `health_checks` are probed.
4. **The `health_checks` table will remain empty for real devices** unless the
   device agent or a background job populates it. Consider either:
   - Having the device agent report health_check results to the server (it already
     runs health checks as commands — store those results in `health_checks`).
   - Or removing the `health_checks` probe from Gate A for real-device
     deployments and relying on `device_metrics` only.

### Verdict

Gate A is working correctly. No changes needed beyond the minor improvements
above. It correctly gates on infrastructure availability.

---

## Gate B — Data Integrity

### What it checks

1. **Completeness** (`B.completeness`): Null ratio of key metrics (cpu, memory,
   disk, latency) within tolerance (1%).
2. **Freshness** (`B.freshness`): Last telemetry sample age ≤ 300s (5-minute
   heartbeat baseline).
3. **Continuity** (`B.continuity`): Max inter-arrival gap between health_check
   samples ≤ 1800s (relaxed from paper's 60s).
4. **Gap checks** (`B.gap_checks`): No sustained discontinuities > 3600s.
5. **Validity** (`B.validity`): No range violations (CPU/Memory/Disk outside
   [0, 100]).
6. **Device digest** (`B.device_digest`): Per-device integrity digest (informational).

### Real-device observations

- **Completeness: Pass.** 3 null values within 1% tolerance over 2804 rows.
- **Freshness: Pass.** Last telemetry 29–30s old (threshold 300s). Real device
  sends heartbeats regularly.
- **Continuity: Fail → fixed.** "Insufficient health_check samples in window to
  assess continuity." The `health_checks` table has 0 rows for real devices
  (no simulated agent manager polling). Fixed in PR #780 by treating < 2 samples
  as "not assessed" (pass) instead of failing.
- **Gap checks: Fail → fixed.** Same root cause as continuity.
- **Validity: Pass.** 0 range violations.
- **Device digest: Pass.** Attached (informational).
- **Trust impact:** Before fix: 0.667 (2 of 3 sub-checks failing). After fix:
  full pass (1.0).

### Recommendations

1. **The continuity/gap fix is a workaround, not a solution.** Treating
   insufficient samples as "pass" means Gate B never actually assesses
   continuity for real devices. The real fix is to populate `health_checks` from
   the device agent's health_check commands (the device already runs them and
   reports results — the backend just needs to store them in `health_checks`).
2. **The 300s freshness threshold is reasonable** for real devices (heartbeats
   every ~30s). No change needed.
3. **The 1800s continuity gap threshold** (relaxed from paper's 60s) is
   appropriate for real devices with irregular heartbeats. But it's never
   actually tested on real data. Consider lowering it once health_checks are
   populated.
4. **The 1% completeness tolerance** is reasonable. Real devices occasionally
   miss a metric (null). No change needed.
5. **Consider adding a network-latency validity check.** The device has persistent
   latency of 267–350ms (threshold 200ms). This isn't currently a Gate B check,
   but it could be. The AI noticed it in its rationale, which is good — but the
   gate should also flag it.

### Verdict

Gate B passes on real devices after the workaround, but the continuity/gap
checks are effectively disabled for real devices. The real fix (populate
health_checks) is a prerequisite for Gate B to provide meaningful data integrity
validation on real devices.

---

## Gate C — Context Readiness

### What it checks

1. **Stable content blocks** (`C.stable_content_blocks`): All required section
   headers (default: `[CURRENT SYSTEM STATUS]`) are present in the assembled
   context.
2. **ID rules** (`C.id_rules`): Alert ID references in the context match the
   known alert IDs (no fabricated IDs). Skipped if no allowlist supplied.
3. **Bounded context** (`C.bounded_context`): Assembled context ≤ 16,000 chars
   (~4k tokens). Low-relevance extras are trimmed to stay under the bound
   (see `docs/ai-validation-gates.md`).

### Real-device observations

- **Stable content blocks: Pass.** All required headers present.
- **ID rules: Pass (skipped).** No known-ID allowlist supplied, so cross-check
  skipped. This means the gate doesn't actually verify ID integrity in practice.
- **Bounded context: Pass.** Context is 9,486 chars (well under 16,000).
- **Trust impact:** Full credit (1.0).

### Recommendations

1. **The ID rules check is effectively disabled** (always skipped because no
   allowlist is supplied). Either supply the known alert IDs from the database,
   or remove the check to avoid false confidence.
2. **The 16,000-char context bound** is reasonable for the current context
   assembly (9,486 chars observed). No change needed. But as more tools are
   added (fleet-wide, more device data), the context could grow. Monitor this.
3. **Consider adding a check for context determinism** — the gate's docstring
   mentions "deterministic, ID-bound" context, but only checks for stable blocks
   and bounded size. A determinism check (same input → same output) would be
   valuable but is hard to test automatically.

### Verdict

Gate C passes on real devices. The ID rules check is a no-op in practice.
Low priority for tuning.

---

## Gate D — Permission and Capability

### What it checks

1. **Capabilities defined** (`D.capabilities_defined`): Device has a capabilities
   dict.
2. **Permissions defined** (`D.permissions_defined`): Device has a permissions
   dict.
3. **Permissions within capabilities** (`D.permissions_within_capabilities`):
   Every permission granted is backed by a capability.

### Real-device observations

- **All checks: Pass.** Brunel Device 001 has `root_access: true` and all
  required permissions (`command_execution`, `process_monitoring`,
  `filesystem_access`, `network_monitoring`).
- **Trust impact:** Full credit (1.0).

### Recommendations

1. **Gate D is working correctly.** It ensures the AI doesn't recommend actions
   the device can't perform. No changes needed.
2. **Consider adding a check for the AI tool RBAC scope** — currently Gate D
   checks device-level permissions, but the AI tool scope (`_check_device_access`
   in `ai/tools.py`) is a separate check. They should be aligned. We already
   fixed the admin role mapping (PR #779) which was a symptom of this gap.
3. **The `trust_ceiling` for Mode 4 (permission gap) is 0.75.** This is
   reasonable — if permissions are inconsistent, the AI can still provide
   analytic summaries but not actionable recommendations.

### Verdict

Gate D is working correctly and provides meaningful validation. No changes
needed.

---

## Gate E — Lifecycle Integrity

### What it checks

1. **Lifecycle state** (`E.lifecycle_state`): Device is in `active` state.
2. **Health state** (`E.health_state`): Device health is `healthy` (not `error`
   or `unknown`).
3. **Credential health** (`E.credential_health`): Device has at least one active
   credential.

### Real-device observations

- **Lifecycle state: Pass.** Device is `active`.
- **Health state: Pass.** Device is `healthy`.
- **Credential health: Pass.** Device has active credentials.
- **Trust impact:** Full credit (1.0).

### Recommendations

1. **Gate E is working correctly.** It prevents the AI from making
   recommendations for suspended, retired, or unhealthy devices.
2. **The `trust_ceiling` for Mode 5 (lifecycle halt) is 0.50.** This is
   reasonable — if the device is compromised, the AI can still provide
   analytic summaries but not actionable recommendations.
3. **Consider checking `is_active` flag** in addition to `lifecycle_state`.
   Currently only `lifecycle_state == "active"` is checked. The `is_active` flag
   (set to False on unpair/suspend) is a separate field. They should be aligned.

### Verdict

Gate E is working correctly. No changes needed.

---

## Cross-cutting observations

### 1. Trust score overconfidence (calibration gap)

The most important finding from the real-device data:

| Trust band | Plans | Avg trust | Observed success | Gap |
|------------|-------|-----------|------------------|-----|
| 0.40–0.60 | 7 | 0.50 | 28.6% | +0.21 |
| 0.80–1.00 | 8 | 1.00 | 62.5% | +0.38 |

The trust score consistently overestimates actual success. This is because:
- The gate scoring model (`achieved / total_weight`) gives full credit when all
  gates pass, but passing gates only means "data is trustworthy," not "the
  action will succeed."
- The trust score conflates **data quality** (gates A–E) with **action
  success probability** (which depends on the device, the command, and the
  environment).

**Recommendation:** Separate the trust score into two components:
- **Data trust** (current trust score): how trustworthy is the context? (Gates A–E)
- **Action confidence** (new): how likely is this action to succeed? (based on
  historical success rate for this action type, device, and site)

The autonomy controller already has the historical data; it just isn't fed back
into the trust score. Consider: `effective_trust = data_trust * action_confidence`.

### 2. Gate B's health_checks dependency

Gate B's continuity and gap checks require `health_checks` rows, which real
devices don't have (the simulated agent manager doesn't poll them). The
workaround (treat < 2 samples as "pass") disables these checks for real devices.

**Recommendation:** Populate `health_checks` from the device agent's health_check
commands. The device already runs health checks and reports results — the
backend just needs to store them in `health_checks` (the command_poller already
has the data; it's just not persisted). This would make Gate B meaningful on
real devices.

### 3. Network latency is not gated

The device has persistent network latency of 267–350ms (threshold 200ms). This
is reported in the AI's rationale and in alerts, but no gate checks it. Consider
adding a network-latency validity check to Gate B or a new Gate F.

### 4. Gate weights are all 1.0

All five gates have equal weight. In practice, Gate A (infrastructure) and Gate
E (lifecycle) are more critical than Gate C (context readiness). Consider
adjusting weights: A=2.0, E=1.5, B=1.0, C=0.5, D=1.0. But this needs
empirical validation.

## Summary of recommended changes

| Priority | Gate | Change | Effort |
|----------|------|--------|--------|
| High | B | Populate `health_checks` from device agent results | Medium |
| High | Cross-cutting | Separate data trust from action confidence in trust score | Medium |
| Medium | A | Add `ai_action_plan`/`ai_action_step` to schema conformance probes | Low |
| Medium | A | Clarify health_checks row count in DB readiness message | Low |
| Medium | D | Align AI tool RBAC scope with device permissions (partially done, PR #779) | Low |
| Medium | E | Check `is_active` flag in addition to `lifecycle_state` | Low |
| Low | B | Add network-latency validity check | Low |
| Low | C | Supply known alert IDs for ID rules cross-check | Medium |
| Low | All | Adjust gate weights based on empirical data | Medium |

## Status

**Discussion only.** No code changes. The gates are functioning correctly on real
devices. The main improvements needed are:
1. Populating `health_checks` for real devices (makes Gate B meaningful).
2. Separating data trust from action confidence (fixes calibration gap).
3. Minor threshold/weight tuning based on more data.
PYEOF
echo written