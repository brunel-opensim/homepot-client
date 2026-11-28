# Study 4 — Extended Anomaly Detector Sensitivity

**Status:** Implemented (not yet executed).  
**Script:** `uq/study4_extended/run_extended_uq.py`  
**Model wrapper:** `uq/study4_extended/anomaly_runner.py`  
**Model under analysis:** `ai/anomaly_detection.py` — `AnomalyDetector.check_anomaly()` (extended)

> For setup instructions and an overview of all studies, see [UQ Overview](overview.md).

---

## Table of Contents

1. [Study purpose](#study-purpose)
2. [Background and motivation](#background-and-motivation)
3. [Methodology](#methodology)
4. [Input distributions per scenario](#input-distributions-per-scenario)
5. [How the pipeline works end-to-end](#how-the-pipeline-works-end-to-end)
6. [Expected results](#expected-results)
7. [Key questions this study answers](#key-questions-this-study-answers)
8. [Recommendations](#recommendations)

---

## Study purpose

Study 4 extends Study 2's scenario boundary validation to the **full 11-input detector**.
Studies 1 and 2 analyse the detector with its original seven metrics (CPU, memory, disk,
error rate, latency, flapping, consecutive failures). PR #1099 added four new device-
health signals to the detector — battery, temperature, CPU speed (throttling), and
Wi-Fi signal strength. Study 4 asks whether those new signals behave correctly across
the same six simulator scenarios.

Specifically, Study 4 looks at three things:

1. **Extended separation:** whether adding the new signals changes the score
   distributions or alert rates for any scenario.
2. **New-signal driver attribution:** which of the four new parameters (battery,
   temperature, CPU speed, Wi-Fi signal) actually drives score variance within each
   scenario, via Sobol indices.
3. **Threshold calibration:** whether the new thresholds (battery ≤ 20%, temp > 85°C,
   throttle ratio < 0.5, Wi-Fi < −80 dBm) produce sensible fire probabilities
   across the scenario ranges.

This study complements Study 2 (which stays on the original seven params as a
regression baseline) and Study 1 (which stays on PCE for global sensitivity of the
original seven). Study 4 uses MCSampler/Saltelli because PCE order 2 at 11 inputs
would require ~177 000 samples.

---

## Background and motivation

The `AnomalyDetector` in `ai/anomaly_detection.py` was extended in PR #1099 with
four new device-health signals:

| Signal | Metric key | Threshold | Score added if triggered |
|---|---|---|---|
| Low battery | `battery_percent` | ≤ 20% (and not charging) | **+0.30** |
| High temperature | `cpu_temp_c` / `system_temp_c` | > 85°C | **+0.30** |
| CPU throttling | `cpu_speed_mhz` / `cpu_speed_max_mhz` | ratio < 0.5 | **+0.20** |
| Weak Wi-Fi signal | `wifi_signal_dbm` | < −80 dBm | **+0.20** |

These thresholds are defined in `ai/config.yaml` under `anomaly_detection.thresholds`
and have sensible defaults in `anomaly_detection.py`.

The four signals are collected by the device agent (PR #1098 for network throughput,
RSSI, and active connections; PR #1099 for battery, temperature, and CPU speed) and
persisted in `DeviceMetrics.extra_metrics`. The background anomaly scan reads them
from `extra_metrics` and passes them to `check_anomaly()`.

The key questions for Study 4 are:

1. **Do the new signals fire in the right scenarios?** (e.g. degraded devices should
   trigger battery/temp/speed/signal anomalies; healthy devices should not.)
2. **Which new signal dominates score variance in each scenario?** (Sobol indices.)
3. **Are the thresholds well-calibrated?** (Fire probabilities should be in the
   20–80% range for meaningful variance, not near 0% or 100%.)

---

## Methodology

### Why EasyVVUQ MCSampler (not PCE)

Study 4 uses the same Saltelli/MCSampler approach as Study 2. PCE order 2 with 11
inputs would require 3¹¹ ≈ 177 000 samples, which is infeasible. MCSampler with
Saltelli gives ~3 300 samples per scenario (N_MC = 300, d = 11, total = 300 × 13).

The `AnomalyDetector` is piecewise-constant (threshold comparisons), so polynomial
surrogates (PCE/SC) would need very high order to approximate discontinuities.
Plain MC (Saltelli plan) is unbiased and free of Gibbs-like artefacts.

### Sampling plan

- **d = 11** inputs per scenario, **N_MC = 300** → 11 × 300 = **3 300 Saltelli samples per scenario**
- 6 scenarios × 3 300 = **19 800 total `AnomalyDetector` calls**
- Continuous `cp.Uniform` distributions for all inputs; fixed parameters use
  `cp.Uniform(x, x)` (constant) so they participate in the Saltelli plan.
- `cpu_speed_max_mhz` is fixed at 2 400 MHz (a typical POS terminal nominal speed).
- Executed with `ThreadPoolExecutor(max_workers=4)` to bound concurrent subprocess count.

### Input distributions per scenario

For each scenario, the 11 `AnomalyDetector` inputs are assigned `cp.Uniform`
distributions. The original 7 match Study 2 (derived from
`_generate_metrics_for_scenario()`). The 4 new params have scenario-appropriate
ranges designed to exercise both sides of the detector's new thresholds:

| Scenario | battery % | CPU temp °C | CPU speed MHz | Wi-Fi dBm |
|---|---|---|---|---|
| healthy | 80–100 | 40–60 | 2000–2400 | −50 to −30 |
| high_cpu | 60–85 | 70–85 | 1800–2300 | −55 to −40 |
| low_memory | 50–75 | 55–70 | 1900–2300 | −60 to −45 |
| high_errors | 40–70 | 60–75 | 1700–2200 | −70 to −50 |
| degraded | 10–50 | 80–95 | 800–1400 | −90 to −70 |
| offline | 0–ε | 0–ε | 0–ε | −100 to −99 |

*ε = 0.001; near-zero range preserves the Saltelli plan without crossing thresholds.*

The original 7 params (cpu, memory, disk, error_rate, latency, flapping,
consecutive_failures) use the same ranges as Study 2.

### How the pipeline works end-to-end

```
EasyVVUQ campaign  (run_extended_uq.py)
│
├─ MCSampler (Saltelli) → 3 300 input combinations per scenario
│
├─ GenericEncoder        → writes each set of values into input.json
│                           (template: anomaly_runner.template)
│
├─ ExecuteLocal          → for each sample, runs:
│                              anomaly_runner.py
│                                  reads input.json
│                                  calls AnomalyDetector.check_anomaly()
│                                  writes output.json
│
├─ JSONDecoder           → collects results into campaign database
│
└─ QMCAnalysis           → computes from Saltelli samples:
                               - mean, std, percentiles of anomaly_score
                               - first-order Sobol indices for all 11 inputs
                               - bootstrap-based uncertainty estimates internally
```

### Run

```bash
# From the homepot-client root:
HOMEPOT_PATH=$(pwd) .venv/bin/python uq/study4_extended/run_extended_uq.py
```

---

## Expected results

The study has not yet been executed (EasyVVUQ is not installed in this environment).
Based on the detector's logic, the expected behaviour is:

### Score distributions

| Scenario | Expected mean | New signals that fire | Rationale |
|---|---|---|---|
| healthy | ~0.0 | none | All metrics below thresholds |
| high_cpu | ~0.1 | none (temp 70–85°C, below 85°C) | CPU spike alone; temp stays below threshold |
| low_memory | ~0.6 | none | Memory pressure + error rate |
| high_errors | ~0.75 | none | Error rate + consecutive failures |
| degraded | ~0.97+ | battery (25%), temp (67%), speed (67%), signal (50%) | Multiple signals straddle thresholds |
| offline | ~1.0 | battery (100%), speed (100%), signal (100%) | All device-health checks fire on top of stability checks |

### Sobol indices (expected)

- **degraded**: the new signals (battery, temp, speed, signal) should show non-zero
  Sobol indices, revealing which device-health parameter drives variance in the
  degraded scenario. The original drivers (consecutive_failures, flapping) should
  remain dominant.
- **healthy / high_cpu / low_memory / high_errors**: the new signals should have
  Sobol ≈ 0 (they don't fire in these scenarios, so no variance contribution).
- **offline**: the new signals that always fire (battery, speed, signal) will have
  Sobol ≈ 0 (constant contribution, no variance). CPU temp will also be ~0 (never fires).

### Key questions this study answers

1. **Do the new thresholds produce sensible fire probabilities?** After the range
   adjustments, degraded scenario fire probabilities are 25–67% (meaningful variance).
   Healthy/high_cpu/low_memory/high_errors fire probabilities are 0% (no false
   positives in those regimes). This is the desired calibration.

2. **Which new signal dominates score variance?** In the degraded scenario, temperature
   and CPU speed both straddle at 67%, so their Sobol indices will reveal which one
   drives more variance. Battery (25%) and Wi-Fi signal (50%) provide additional
   variance.

3. **Are the new signals redundant with existing ones?** If battery/temp/speed/signal
   Sobol indices are near zero in all scenarios, the signals add no information beyond
   the existing 7 params. If they're non-zero in degraded, they provide new
   discriminative power.

---

## Key findings (to be populated after execution)

*This section will be filled in once the study is run with EasyVVUQ installed.*

---

## Recommendations (preliminary)

1. **The range adjustments (battery 10–50, signal −90 to −70 in degraded) are necessary**
   to create meaningful variance. Without them, battery (20–50) never fires (P=0) and
   signal (−95 to −80) always fires (P=100%), making both Sobol indices ≈ 0.

2. **The `high_cpu` temperature range (70–85°C) does not straddle the 85°C threshold**
   (P=0). This is intentional — high CPU usage doesn't necessarily mean overheating.
   If the goal is to test thermal throttling under high CPU, consider extending the
   range to 75–90°C.

3. **The `offline` scenario's CPU speed (near 0) triggers throttling** (P=100%), which
   is a quirk of the detector (0 MHz < 1200 MHz threshold). This is consistent with
   the other "always-off" params. The Sobol index will be ~0.

4. **Study 4 complements Study 2** (which stays on the original 7 params). Together
   they answer: "which inputs matter most" (Study 2, 7 params) and "do the new
   device-health signals add discriminative power" (Study 4, 11 params).

5. **When PR 2's new params are added to Study 2**, the study should be re-run to
   confirm the new signals don't break the existing scenario separation.
