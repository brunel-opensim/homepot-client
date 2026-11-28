"""push_runner.py — EasyVVUQ runner for Study 3 (push notification reliability).

Reads ``input.json`` (written by the EasyVVUQ encoder from push_runner.template),
computes the three deterministic expected-value outputs, then writes
``output.json`` back so the EasyVVUQ decoder can collate the results.

Deterministic expected-value model
-----------------------------------
Let  p = success_rate       (base per-device success probability, ~ Beta(19,1))
     n = num_devices        (total devices in the fleet, integer ≥ 1)
     d = delivery_delay_ms  (typical per-device delivery delay, ms)
     l = network_latency_ms (network round-trip latency, ms)
     s = wifi_signal_dbm    (Wi-Fi signal strength, dBm; more negative = weaker)

Network quality degrades the effective success rate:
  latency_penalty  = min(l / 500, 0.3)           # up to 30% from high latency
  signal_penalty   = max(0, min((-s - 70) / 30, 0.3))  # up to 30% from weak signal
  effective_p      = max(0.1, p - latency_penalty - signal_penalty)

  expected_failures = n * (1 - effective_p)
  failure_rate      = 1 - effective_p
  campaign_time_ms  = 100 + d * n / (n + 1)      (saturation model, scaled by delay)

Using expected values (rather than a random binomial draw) keeps the model
deterministic so that the Sobol variance decomposition is well-defined:
P(at least k succeed) is computed post-collation from the collated samples
using scipy.stats.binom.cdf once all samples are gathered.
"""

import json

# ── Load inputs ──────────────────────────────────────────────────────────────
with open("input.json") as fh:
    data = json.load(fh)

# EasyVVUQ injects an "outfile" field; ignore it.
data.pop("outfile", None)

success_rate = float(data["success_rate"])
num_devices = max(1, int(round(float(data["num_devices"]))))
delivery_delay_ms = float(data["delivery_delay_ms"])
network_latency_ms = float(data["network_latency_ms"])
wifi_signal_dbm = float(data["wifi_signal_dbm"])

# Clamp success_rate to [0, 1) to avoid degenerate 0-failure outputs for p≥1
success_rate = min(max(success_rate, 0.0), 1.0 - 1e-9)

# ── Network quality penalty (best-effort model of delivery degradation) ───────
# Higher latency and weaker signal reduce the effective success rate.
latency_penalty = min(network_latency_ms / 500.0, 0.3)
signal_penalty = max(0.0, min((-wifi_signal_dbm - 70.0) / 30.0, 0.3))

# ── Effective success rate (floor at 0.1 to avoid degenerate cases) ───────────
effective_p = max(0.1, success_rate - latency_penalty - signal_penalty)

# ── Compute outputs ──────────────────────────────────────────────────────────
expected_failures = num_devices * (1.0 - effective_p)
failure_rate = 1.0 - effective_p
campaign_time_ms = 100.0 + delivery_delay_ms * num_devices / (num_devices + 1.0)

# ── Write outputs ─────────────────────────────────────────────────────────────
with open("output.json", "w") as fh:
    json.dump(
        {
            "expected_failures": expected_failures,
            "failure_rate": failure_rate,
            "campaign_time_ms": campaign_time_ms,
        },
        fh,
    )
