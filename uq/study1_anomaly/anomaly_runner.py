"""Thin shim delegating to the shared anomaly runner.

EasyVVUQ invokes this file directly from an isolated working directory, so it
must remain a real script (not a symlink). The shared implementation lives in
``uq/common/runner.py``; any change to the casting/output logic should be made
there so both studies stay in sync.
"""

import os
import sys

_HOMEPOT_PATH = os.environ.get(
    "HOMEPOT_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)
if _HOMEPOT_PATH not in sys.path:
    sys.path.insert(0, _HOMEPOT_PATH)
sys.path.insert(0, os.path.join(_HOMEPOT_PATH, "uq", "common"))

from runner import run_anomaly  # noqa: E402

FLOAT_KEYS = [
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "error_rate",
    "network_latency_ms",
]
INT_KEYS = ["flapping_count", "consecutive_failures"]

run_anomaly(FLOAT_KEYS, INT_KEYS)
