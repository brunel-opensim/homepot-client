"""Shared runner logic for the anomaly-detector UQ studies.

Each study provides a thin ``anomaly_runner.py`` shim that declares its input
parameter keys and delegates to :func:`run_anomaly`, so the casting and
output-writing logic lives in one place.  EasyVVUQ invokes the shim directly
from an isolated working directory, so the shim must remain a real script.
"""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.WARNING)

_HOMEPOT_PATH = os.environ.get(
    "HOMEPOT_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)
if _HOMEPOT_PATH not in sys.path:
    sys.path.insert(0, _HOMEPOT_PATH)

from ai.anomaly_detection import AnomalyDetector  # noqa: E402


def run_anomaly(float_keys: list[str], int_keys: list[str]) -> None:
    """Read ``input.json``, run the anomaly detector, write ``output.json``."""
    with open("input.json") as fh:
        metrics = json.load(fh)

    # GenericEncoder injects an "outfile" key — remove it before scoring.
    metrics.pop("outfile", None)

    # Cast to appropriate types (the encoder writes everything as strings in
    # some modes).
    for k in float_keys:
        if k in metrics:
            metrics[k] = float(metrics[k])
    for k in int_keys:
        if k in metrics:
            metrics[k] = int(round(float(metrics[k])))

    detector = AnomalyDetector()
    anomaly_score, anomaly_list = detector.check_anomaly(metrics)

    output = {
        "anomaly_score": anomaly_score,
        "num_anomalies": len(anomaly_list),
    }
    with open("output.json", "w") as fh:
        json.dump(output, fh)

    print(f"anomaly_score={anomaly_score:.4f}  num_anomalies={len(anomaly_list)}")
