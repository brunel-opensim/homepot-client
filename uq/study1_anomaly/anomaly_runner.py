"""Thin model wrapper for EasyVVUQ.

EasyVVUQ runs this script once per sample, each time in an isolated working
directory that already contains a populated ``input.json`` file.  The script:

1. Reads ``input.json`` (written by EasyVVUQ's GenericEncoder).
2. Calls ``AnomalyDetector.check_anomaly()`` from ``ai/anomaly_detection.py``.
3. Writes the scalar QoIs to ``output.json`` (parsed by EasyVVUQ's JSONDecoder).

Usage (normally invoked automatically by EasyVVUQ, but also runnable manually):

    HOMEPOT_PATH=/path/to/homepot-client python anomaly_runner.py

``HOMEPOT_PATH`` defaults to two directories above this script's location
(i.e. the homepot-client root), so you only need to set it explicitly if you
keep the ``uq/`` folder somewhere non-standard.
"""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------------------
# Locate the homepot-client root so we can import from ai/
# ---------------------------------------------------------------------------
_HOMEPOT_PATH = os.environ.get(
    "HOMEPOT_PATH",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)
if _HOMEPOT_PATH not in sys.path:
    sys.path.insert(0, _HOMEPOT_PATH)

try:
    from ai.anomaly_detection import AnomalyDetector
except ImportError as exc:
    print(
        f"ERROR: Could not import AnomalyDetector from {_HOMEPOT_PATH}/ai/. "
        "Set the HOMEPOT_PATH environment variable to the homepot-client root.",
        file=sys.stderr,
    )
    raise exc

# ---------------------------------------------------------------------------
# Read sample inputs written by EasyVVUQ's GenericEncoder
# ---------------------------------------------------------------------------
with open("input.json") as fh:
    metrics = json.load(fh)

# GenericEncoder injects an "outfile" key — remove it before passing to the model
metrics.pop("outfile", None)

# Cast to appropriate types (encoder writes everything as strings in some modes)
float_keys = [
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "error_rate",
    "network_latency_ms",
]
int_keys = ["flapping_count", "consecutive_failures"]

for k in float_keys:
    if k in metrics:
        metrics[k] = float(metrics[k])
for k in int_keys:
    if k in metrics:
        metrics[k] = int(round(float(metrics[k])))

# ---------------------------------------------------------------------------
# Run the model
# ---------------------------------------------------------------------------
detector = AnomalyDetector()
anomaly_score, anomaly_list = detector.check_anomaly(metrics)

# ---------------------------------------------------------------------------
# Write QoIs for EasyVVUQ's JSONDecoder
# ---------------------------------------------------------------------------
output = {
    "anomaly_score": anomaly_score,
    "num_anomalies": len(anomaly_list),
}

with open("output.json", "w") as fh:
    json.dump(output, fh)

print(f"anomaly_score={anomaly_score:.4f}  num_anomalies={len(anomaly_list)}")
