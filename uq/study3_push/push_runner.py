"""push_runner.py — EasyVVUQ runner for Study 3 (push notification reliability).

Reads ``input.json`` (written by the EasyVVUQ encoder from push_runner.template),
computes the three deterministic expected-value outputs, then writes
``output.json`` back so the EasyVVUQ decoder can collate the results.

Deterministic expected-value model
-----------------------------------
Let  p = success_rate  (fraction of devices receiving the notification)
     n = num_devices   (total devices in the fleet, integer ≥ 1)

  expected_failures = n * (1 - p)
  failure_rate      = 1 - p
  campaign_time_ms  = 100 + 400 * n / (n + 1)   (saturation model)

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

# Clamp success_rate to [0, 1) to avoid degenerate 0-failure outputs for p≥1
success_rate = min(max(success_rate, 0.0), 1.0 - 1e-9)

# ── Compute outputs ──────────────────────────────────────────────────────────
expected_failures = num_devices * (1.0 - success_rate)
failure_rate = 1.0 - success_rate
campaign_time_ms = 100.0 + 400.0 * num_devices / (num_devices + 1.0)

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
