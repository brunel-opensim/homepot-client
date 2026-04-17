"""EasyVVUQ campaign: Sobol sensitivity analysis of AnomalyDetector.

This script runs Idea 1 from VVUQ_PLAN.md:
  * Input parameters:  7 device health metrics (Uniform distributions)
  * Model:             ai/anomaly_detection.py  AnomalyDetector.check_anomaly()
  * QoIs:              anomaly_score (0-1), num_anomalies (int)
  * Analysis:          Polynomial Chaos Expansion (order 2), Sobol indices

Prerequisites
-------------
1. Install EasyVVUQ in editable mode into the homepot venv (one-time setup):

       cd homepot-client
       .venv/bin/pip install -e /path/to/EasyVVUQ

   This installs easyvvuq and all its dependencies (chaospy, dill, etc.)
   directly into the homepot venv — no separate venv needed.

2. HOMEPOT_PATH (optional) — defaults to the homepot-client root detected
   from this script's location.  Set it explicitly if needed:

       export HOMEPOT_PATH=/path/to/homepot-client

Run
---
    # From the homepot-client root:
    .venv/bin/python uq/study1_anomaly/run_anomaly_uq.py

    # Or with the venv activated:
    python uq/study1_anomaly/run_anomaly_uq.py

Results are printed to stdout and (if matplotlib is available) saved as PNG
files inside uq/study1_anomaly/figs/.
"""

import os
from shutil import rmtree
import sys

try:
    import chaospy as cp
    import easyvvuq as uq
except ImportError as exc:
    print(
        "\nERROR: Could not import easyvvuq or chaospy.\n"
        "  Install EasyVVUQ into this venv with:\n"
        "    .venv/bin/pip install -e /path/to/EasyVVUQ\n"
        "  (clone from https://github.com/UCL-CCS/EasyVVUQ if you don't have it)\n"
    )
    raise exc

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
UQ_DIR = os.path.dirname(os.path.abspath(__file__))
HOMEPOT_ROOT = os.environ.get(
    "HOMEPOT_PATH",
    os.path.abspath(
        os.path.join(UQ_DIR, "../..")
    ),  # script is uq/study1_anomaly/ → root is two levels up
)

CAMPAIGN_WORK_DIR = os.path.join(UQ_DIR, "campaign_anomaly_uq")
FIGS_DIR = os.path.join(UQ_DIR, "figs")
TEMPLATE_FILE = os.path.join(UQ_DIR, "anomaly_runner.template")
RUNNER_SCRIPT = os.path.join(UQ_DIR, "anomaly_runner.py")

# Clean up any previous campaign run so we start fresh
if os.path.exists(CAMPAIGN_WORK_DIR):
    rmtree(CAMPAIGN_WORK_DIR)
os.makedirs(CAMPAIGN_WORK_DIR)
os.makedirs(FIGS_DIR, exist_ok=True)

print(f"[INFO] Campaign work dir: {CAMPAIGN_WORK_DIR}")
print(f"[INFO] Homepot root:      {HOMEPOT_ROOT}")

# ---------------------------------------------------------------------------
# Parameter space
# ---------------------------------------------------------------------------
# All seven metrics fed to AnomalyDetector.check_anomaly().
# Uniform distributions spanning a physically plausible range that straddles
# each threshold so we can observe how the score responds on both sides.
#
# Thresholds (from ai/config.yaml):
#   cpu_percent: 90, memory_percent: 90, disk_percent: 90
#   error_rate: 0.05, network_latency_ms: 200
#   flapping_count: 5, consecutive_failures: 3

params = {
    "cpu_percent": {"type": "float", "min": 5.0, "max": 100.0, "default": 50.0},
    "memory_percent": {"type": "float", "min": 10.0, "max": 100.0, "default": 50.0},
    "disk_percent": {"type": "float", "min": 10.0, "max": 100.0, "default": 50.0},
    "error_rate": {"type": "float", "min": 0.0, "max": 0.50, "default": 0.05},
    "network_latency_ms": {
        "type": "float",
        "min": 10.0,
        "max": 1000.0,
        "default": 150.0,
    },
    "flapping_count": {"type": "float", "min": 0.0, "max": 10.0, "default": 2.0},
    "consecutive_failures": {"type": "float", "min": 0.0, "max": 15.0, "default": 2.0},
    "outfile": {"type": "string", "default": "output.json"},
}

# Ranges and distribution rationale: see VVUQ_PLAN.md §3.2 "Input distributions".
# Key formula: P(fires) = (b - T) / (b - a)  for Uniform(a,b) with threshold T.
# Sobol index collapses toward 0 at both extremes (fires never OR fires always).
vary = {
    "cpu_percent": cp.Uniform(5.0, 100.0),
    "memory_percent": cp.Uniform(10.0, 100.0),
    "disk_percent": cp.Uniform(10.0, 100.0),
    "error_rate": cp.Uniform(0.0, 0.50),
    "network_latency_ms": cp.Uniform(10.0, 1000.0),
    "flapping_count": cp.Uniform(0.0, 10.0),
    "consecutive_failures": cp.Uniform(0.0, 15.0),
}


# ---------------------------------------------------------------------------
# Encoder / Decoder / Execute
# ---------------------------------------------------------------------------
encoder = uq.encoders.GenericEncoder(
    template_fname=TEMPLATE_FILE,
    delimiter="$",
    target_filename="input.json",
)

decoder = uq.decoders.JSONDecoder(
    target_filename="output.json",
    output_columns=["anomaly_score", "num_anomalies"],
)

# Pass HOMEPOT_PATH so the runner can find ai/anomaly_detection.py.
# The HOMEPOT_PATH env var is inherited by child processes automatically,
# but we set it explicitly here for clarity.
os.environ.setdefault("HOMEPOT_PATH", HOMEPOT_ROOT)

execute = uq.actions.ExecuteLocal(f"{sys.executable} {RUNNER_SCRIPT}")

actions = uq.actions.Actions(
    uq.actions.CreateRunDirectory(root=CAMPAIGN_WORK_DIR, flatten=True),
    uq.actions.Encode(encoder),
    execute,
    uq.actions.Decode(decoder),
)

# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------
campaign = uq.Campaign(
    name="anomaly_uq",
    params=params,
    actions=actions,
    work_dir=CAMPAIGN_WORK_DIR,
)

# ---------------------------------------------------------------------------
# PCE Sampler
# ---------------------------------------------------------------------------
# polynomial_order=2 with 7 inputs:
POLY_ORDER = 2

sampler = uq.sampling.PCESampler(vary=vary, polynomial_order=POLY_ORDER)
campaign.set_sampler(sampler)
campaign.draw_samples()

n_samples = campaign.get_active_sampler().n_samples
print(f"[INFO] PCE order {POLY_ORDER} → {n_samples} samples drawn")

# ---------------------------------------------------------------------------
# Execute & collate
# ---------------------------------------------------------------------------
print("[INFO] Running model evaluations ...")
campaign.execute().collate()
print("[INFO] All samples complete.")

# ---------------------------------------------------------------------------
# PCE Analysis
# ---------------------------------------------------------------------------
analysis = uq.analysis.PCEAnalysis(
    sampler=sampler,
    qoi_cols=["anomaly_score", "num_anomalies"],
)
campaign.apply_analysis(analysis)
results = campaign.get_last_analysis()

# ---------------------------------------------------------------------------
# Print results
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("ANOMALY SCORE — statistical summary")
print("=" * 60)
for stat in ("mean", "std", "10%", "90%"):
    val = results.describe("anomaly_score", stat)
    # describe() may return a 0-d or 1-d numpy array; extract scalar
    val = float(np.atleast_1d(val).flat[0])
    print(f"  {stat:<8} {val:.4f}")

print("\n" + "=" * 60)
print("FIRST-ORDER SOBOL INDICES  (fraction of variance explained)")
print("=" * 60)
sobols = results.sobols_first("anomaly_score")
# Values may be 0-d arrays; convert to plain floats for display
sobols_scalar = {k: float(np.atleast_1d(v).flat[0]) for k, v in sobols.items()}
for param, idx in sorted(sobols_scalar.items(), key=lambda x: -x[1]):
    bar = "#" * int(round(idx * 40))
    print(f"  {param:<25} {idx:.4f}  {bar}")

print("\nNOTE: dominant parameters (high Sobol index) are the primary")
print("drivers of score uncertainty — these deserve the most monitoring.")

# ---------------------------------------------------------------------------
# Plot (optional — skip gracefully if matplotlib not available)
# ---------------------------------------------------------------------------
try:
    import matplotlib.pyplot as plt

    def _label(param: str) -> str:
        """Convert snake_case param name to sentence-case label with spaces."""
        acronyms = {"cpu"}
        words = param.replace("_", " ").split()
        words[0] = words[0].capitalize()
        return " ".join(w.upper() if w.lower() in acronyms else w for w in words)

    # 1. Sobol bar chart  (linear scale — indices are bounded [0,1])
    fig, ax = plt.subplots(figsize=(8, 4))
    params_sorted = sorted(sobols_scalar.items(), key=lambda x: x[1])
    names = [_label(p) for p, _ in params_sorted]
    vals = [v for _, v in params_sorted]
    ax.barh(names, vals, color="steelblue")
    ax.set_xlabel("First-order Sobol index")
    ax.set_title(
        "Anomaly score: Sobol sensitivity indices (PCE order {})".format(POLY_ORDER)
    )
    plt.tight_layout()
    sobol_png = os.path.join(FIGS_DIR, "sobol_anomaly_score.png")
    plt.savefig(sobol_png, dpi=150)
    print(f"\n[INFO] Sobol plot saved → {sobol_png}")

    # 2. Output histogram  (log y-scale: score is heavily skewed toward 1.0;
    #    log scale reveals the shape of the lower-score tail that linear hides)
    df = campaign.get_collation_result()
    fig2, ax2 = plt.subplots(figsize=(7, 4))
    ax2.hist(df["anomaly_score"], bins=30, color="steelblue", edgecolor="white")
    ax2.set_yscale("log")
    ax2.set_xlabel("Anomaly score")
    ax2.set_ylabel("Count")
    ax2.set_title("Distribution of anomaly scores across PCE sample space")
    plt.tight_layout()
    hist_png = os.path.join(FIGS_DIR, "hist_anomaly_score.png")
    plt.savefig(hist_png, dpi=150)
    print(f"[INFO] Histogram saved  → {hist_png}")

    plt.close("all")

except ImportError:
    print("\n[INFO] matplotlib not found — skipping plots.")
    print("       Install with:  pip install matplotlib")
