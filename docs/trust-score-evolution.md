# Trust score evolution: implementation roadmap (Stages 2–3)

This document lays out the implementation details for improving the trust score
model beyond Stage 1 (weighted gates). Stages 2 and 3 are triggered by sample
thresholds accumulated during the soak test. They are **not yet implemented** —
this is the specification to follow when the thresholds are met.

## Stage 1 (implemented): Weighted gates

**Status:** Implemented. Gate weights adjusted based on criticality:
- Gate A (Infrastructure): 2.0
- Gate B (Data Integrity): 1.5
- Gate C (Context Readiness): 0.5
- Gate D (Permission): 1.0
- Gate E (Lifecycle): 1.5

Thresholds relaxed for real devices (documented in `gate_b.py`):
- Freshness: 300s (matches paper)
- Completeness: 1% null tolerance (paper: 0; relaxed for real telemetry)
- Continuity gap: 1800s (paper: 60s; relaxed for irregular real-device heartbeats)
- Sustained gap: 3600s

**Trigger:** None (implemented immediately).

---

## Stage 2: Separate scoring dimensions

**Trigger:** ≥ 50 verified runs per action type.

### Problem

The current trust score conflates two different things:
- **Data trust** (gates A–E): how trustworthy is the context?
- **Action confidence**: how likely is this action to succeed?

Gates A–E measure data quality. They do **not** measure whether the action
will succeed. A plan can pass all gates (trust 1.0) but fail because the device
doesn't support the config key, or the network is flaky, or the OS command
errors out. The calibration data confirms this: trust 1.0 → observed 62.5%
success.

### Solution

Split the trust score into two independent scores:

1. **Data trust** (current, from gates): `data_trust = achieved / total_weight`
   — unchanged. Measures context quality.

2. **Action confidence** (new, from reliability metrics): `action_confidence =
   historical_success_rate` for this action type, device, and site. Uses the
   `AIActionOutcome` data already collected.

3. **Effective trust**: `effective_trust = data_trust * action_confidence`

The actionable threshold becomes: `effective_trust >= 0.7` (configurable).

### Implementation steps

1. **Add `action_confidence` to `EnvelopeResult`** in `ai/gates/envelope.py`:
   ```python
   @dataclass
   class EnvelopeResult:
       ...
       data_trust: float
       action_confidence: float
       effective_trust: float  # data_trust * action_confidence
   ```

2. **Feed reliability metrics into the envelope.** The envelope's `run()` method
   currently takes only `GateContext`. Add an optional `reliability` parameter:
   ```python
   async def run(self, context: GateContext, reliability: Optional[Dict] = None) -> EnvelopeResult:
   ```
   Inside, look up `action_confidence` from the reliability data for the action
   being proposed. If no reliability data is available, default to 1.0 (no
   penalty for new actions).

3. **Update the trust score computation.** Replace:
   ```python
   trust_score = raw_score if trust_mode.actionable else min(raw_score, trust_mode.trust_ceiling)
   ```
   with:
   ```python
   data_trust = raw_score if trust_mode.actionable else min(raw_score, trust_mode.trust_ceiling)
   action_confidence = reliability.get(action, {}).get("success_rate", 1.0) if reliability else 1.0
   trust_score = data_trust * action_confidence
   ```

4. **Update the actionable threshold.** Currently `is_actionable` checks
   `trust_mode.actionable`. Change to also check `effective_trust >= 0.7`:
   ```python
   @property
   def is_actionable(self) -> bool:
       return self.trust_mode.actionable and self.effective_trust >= 0.7
   ```

5. **Update the AI query endpoint** (`AIEndpoint.py`) to pass reliability data
   into the envelope. The endpoint already calls `get_ai_action_reliability` for
   the autonomy controller; reuse that data for the envelope.

6. **Update the frontend** to display both scores in the trust badge:
   "Data trust: 0.95, Action confidence: 0.62, Effective: 0.59."

### Files to change

- `ai/gates/envelope.py` — `EnvelopeResult`, `ValidationEnvelope.run()`
- `ai/gates/base.py` — `Mode.actionable` (add threshold)
- `backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py` — pass reliability to envelope
- `frontend/src/pages/AIProposals/AIProposalsList.jsx` — display both scores

### Expected outcome

- Trust scores will better reflect actual success rates.
- The calibration gap (currently +0.38 for high-trust plans) should narrow.
- New actions (0 samples) default to `action_confidence = 1.0` (no penalty),
  so they aren't unfairly penalized before data accumulates.

### Risks

- Requires reliability data to be available at query time (extra DB query).
- The 0.7 threshold is arbitrary — needs tuning with data.
- Technicians may be confused by two scores. Consider showing only
  `effective_trust` in the UI, with `data_trust` and `action_confidence` in
  the details.

---

## Stage 3: Empirical calibration

**Trigger:** ≥ 200 verified runs per action type.

### Problem

Even with separate scoring dimensions, the relationship between trust score and
observed success may not be linear. A trust score of 0.8 might correspond to
70% success, not 80%. The calibration endpoint (`GET /ai/calibration`) already
computes this gap; the trust score just doesn't use it.

### Solution

Use the calibration data to fit a calibration curve (isotonic regression or
Platt scaling) that maps the raw effective trust score to a calibrated
probability. The calibrated score is what gets used for decisions and displayed
to technicians.

### Implementation steps

1. **Add a calibration model** in `ai/calibration.py`:
   ```python
   def calibrate(raw_score: float, calibration_curve: List[Tuple[float, float]]) -> float:
       """Map a raw trust score to a calibrated probability using isotonic regression."""
   ```

2. **Store the calibration curve** in the database (or in memory, refreshed
   periodically). The `get_confidence_calibration` endpoint already computes
   the data; just fit the curve.

3. **Apply calibration in the envelope** before returning the trust score:
   ```python
   trust_score = calibrate(effective_trust, calibration_curve)
   ```

4. **Display calibrated vs. raw** in the UI: "Trust: 0.72 (calibrated from 0.85)."

### Files to change

- `ai/calibration.py` (new) — calibration curve fitting and application
- `ai/gates/envelope.py` — apply calibration
- `backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py` — pass calibration curve
- `frontend/src/pages/AIProposals/AIProposalsList.jsx` — display calibrated score

### Expected outcome

- Trust scores accurately reflect observed success rates.
- The calibration gap (currently +0.38) should approach 0.
- Autonomy thresholds become meaningful: Level 2 (98%) means the AI is
  genuinely 98% likely to succeed.

### Risks

- Requires 200+ samples per action type (may take months on a single device).
- Isotonic regression can overfit on small samples. Use Platt scaling (logistic
  regression) for smaller datasets.
- Complex to explain to technicians. Consider showing only the calibrated score
  in the UI.

---

## Gate threshold tuning (ongoing)

The paper's thresholds (continuity gaps ≤ 60s, completeness null ratio 0) were
designed for simulated devices. Real devices need relaxed thresholds. The
current relaxed values:

| Threshold | Paper value | Real-device value | Rationale |
|-----------|------------|-------------------|-----------|
| Freshness max age | ~300s | 300s | Matches paper; real devices heartbeat every ~30s |
| Continuity gap | 60s | 1800s | Real devices have irregular heartbeats |
| Completeness null ratio | 0 | 0.01 | Real telemetry occasionally misses |
| Sustained gap | 60s | 3600s | Matches paper's "gaps > 60 min" |

### Tuning process

1. After 50+ runs, review the actual continuity gaps and completeness ratios.
2. If real devices consistently achieve 60s continuity gaps, tighten the
   threshold. If not, keep it relaxed and document why.
3. If completeness null ratio is consistently 0, tighten to 0. If not, keep
   at 0.01 or adjust.
4. Update the `TESTING NOTE` / `REAL-DEVICE NOTE` comments in `gate_b.py`
   with the empirical findings.

### Gate weight tuning (after Stage 2)

Once separate scoring dimensions are in place, the gate weights can be tuned
based on which gates are most predictive of action success. Use the reliability
data to compute the correlation between each gate's pass/fail and the observed
success rate. Gates with high correlation get higher weights.

---

## Summary of stages

| Stage | Trigger | Change | Effort | Status |
|-------|---------|--------|--------|--------|
| 1 | None (now) | Weighted gates + threshold docs | Low | **Implemented** |
| 2 | ≥ 50 verified runs/action | Separate data trust from action confidence | Medium | Planned |
| 3 | ≥ 200 verified runs/action | Empirical calibration curve | High | Planned |
| Ongoing | More data | Threshold and weight tuning | Low | Ongoing |

## Files involved

### Stage 1 (done)
- `ai/gates/gate_a.py` — weight 2.0
- `ai/gates/gate_b.py` — weight 1.5, real-device note
- `ai/gates/gate_c.py` — weight 0.5
- `ai/gates/gate_d.py` — weight 1.0
- `ai/gates/gate_e.py` — weight 1.5

### Stage 2 (planned)
- `ai/gates/envelope.py` — add `data_trust`, `action_confidence`, `effective_trust`
- `ai/gates/base.py` — add threshold to `is_actionable`
- `backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py` — pass reliability
- `frontend/src/pages/AIProposals/AIProposalsList.jsx` — display both scores

### Stage 3 (planned)
- `ai/calibration.py` (new) — calibration curve
- `ai/gates/envelope.py` — apply calibration
- `backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py` — pass calibration curve
- `frontend/src/pages/AIProposals/AIProposalsList.jsx` — display calibrated score
PYEOF
echo written