# AI delegation — recommended next steps (post-soak-test)

This document captures the recommended path forward after the first real-device
soak test on Brunel Device 001 (2026-11-05). It pairs with
`docs/ai-delegation-case-study-brunel-001.md` and
`docs/ai-delegation-plan.md` §17.

## Current state

- Full delegation loop proven on real hardware: propose → approve → execute →
  verify → report, with rollback and retry.
- Trust score 1.0 on `health_check` (4+ samples). Autonomy Level 1.
- `update_config` at 37.5% success (8 samples). Autonomy Level 1 but low
  success rate.
- Calibration gap: trust 1.0 → observed 62.5% success (overconfident).
- Auto-execution runner built but disabled (`auto_execute_enabled: false`).
- Phase F (infrastructure delegation) designed but not coded.

## Recommended sequence

### 1. Complete the soak test (immediate, 1–2 days)

Run S2–S8 on Brunel Device 001 to accumulate samples and exercise all
code paths. Target 10+ verified runs across `health_check` and `update_config`.

| Scenario | Action | What it tests |
|----------|--------|---------------|
| S2 | `update_config` (volume, brightness) | Reversible config change + verification |
| S3 | Rollback drill (invalid config value) | Per-key failure → rollback → restore |
| S4 | Retry on transport failure | Backoff scheduling + re-dispatch |
| S5 | Per-step approval (`restart_service`) | T3 gate + retry re-gate |
| S6 | Dry run | Non-destructive preview |
| S7 | Fleet command | Multi-device step tracking |
| S8 | Delegate and report | Full loop: propose → execute → verify → report |

### 2. Tune trust scoring (short term)

- The calibration data shows trust 1.0 → 62.5% actual success. Adjust the
  trust envelope so scores reflect observed success rates.
- Consider: weight Gate B's continuity check more heavily, or add a
  calibration penalty when historical success < predicted trust.
- **Gate:** calibration gap < 0.15 (trust within 15% of observed).

### 3. Enable Level 2 auto-execute for health_check (medium term)

- Once 50+ verified `health_check` runs at ≥ 98% success, flip
  `auto_execute_min_level` to 2 for that action.
- This removes plan-level approval for low-risk diagnostics.
- **Gate:** Level 2 `health_check` runs autonomously with zero human clicks.

### 4. Background execution runner (medium term)

- PR #793 is built but disabled. Enable it once Level 2 is earned.
- Add a per-site toggle so auto-execution can be turned on/off per customer.
- **Gate:** approved plans auto-execute and reach terminal state.

### 5. Phase F — infrastructure delegation (longer term)

- Design doc: `docs/infrastructure-delegation-design.md`.
- Needs: credential broker, command allow-list, security review.
- Start with I1 (read-only diagnostics) behind admin-only access.

### 6. Production readiness

- Implement redaction (security doc option B) before real customer data.
- Enable provider zero-data-retention modes and sign DPAs.
- Full backend test coverage for Phases A–E.

## What to do now

1. Merge pending PRs (#783, #785, #789, #790, #792, #793, #787, #779, #780,
   #775, #776, #788, #781, #784, #785, #786, #778, #773, #772, #771).
2. Deploy.
3. Run S2–S8 on Brunel Device 001 (see `docs/real-device-ai-soak-test.md`).
4. Monitor `/api/v1/ai/reliability`, `/api/v1/ai/autonomy`, `/api/v1/ai/calibration`.
5. After 50+ verified runs, enable Level 2 auto-execute for `health_check`.
PYEOF
echo written