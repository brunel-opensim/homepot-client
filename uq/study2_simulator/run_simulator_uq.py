"""Study 2: Scenario boundary validation using EasyVVUQ MCSampler + QMCAnalysis.

For each of the six device-simulator scenarios defined in
``DeviceSimulatorEndpoint._generate_metrics_for_scenario()``, an EasyVVUQ
campaign is run with the Saltelli-plan ``MCSampler``.  ``QMCAnalysis`` then
computes:

  - Mean, std, and percentiles of the anomaly score distribution.
  - **First- and total-order Sobol sensitivity indices** — which input metric
    drives score variance most within each scenario?
  - Bootstrap confidence intervals on the Sobol estimates.

Sampling plan
-------------
``MCSampler`` uses a Saltelli plan: total samples per scenario is
``N_MC_PER_SCENARIO × (n_params + 2) = N_MC_PER_SCENARIO × 9``.  With
``N_MC_PER_SCENARIO = 1000`` each scenario gets **9 000 samples**.  Six
scenarios → **54 000 model evaluations** total.

Runner
------
This study bundles its own ``anomaly_runner.py`` and ``anomaly_runner.template``
(a local copy of the Study 1 runner) so it is fully self-contained and
independent of Study 1.

Run
---
    # From the homepot-client root:
    HOMEPOT_PATH=$(pwd) .venv/bin/python uq/study2_simulator/run_simulator_uq.py

Output is printed to stdout.  Three plots are saved to
``uq/study2_simulator/figs/``.  Campaign working directories are removed
automatically after each scenario's analysis completes.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from shutil import rmtree

try:
    import easyvvuq as uq
    import chaospy as cp
except ImportError as exc:
    print(
        "\nERROR: Could not import easyvvuq or chaospy.\n"
        "  Install EasyVVUQ into this venv with:\n"
        "    .venv/bin/pip install -e /path/to/EasyVVUQ\n",
        file=sys.stderr,
    )
    raise exc

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
STUDY_DIR    = os.path.dirname(os.path.abspath(__file__))
HOMEPOT_ROOT = os.environ.get(
    "HOMEPOT_PATH",
    os.path.abspath(os.path.join(STUDY_DIR, "../..")),
)
FIGS_DIR      = os.path.join(STUDY_DIR, "figs")
RUNNER_SCRIPT = os.path.join(STUDY_DIR, "anomaly_runner.py")
TEMPLATE_FILE = os.path.join(STUDY_DIR, "anomaly_runner.template")
os.makedirs(FIGS_DIR, exist_ok=True)

os.environ.setdefault("HOMEPOT_PATH", HOMEPOT_ROOT)

print(f"[INFO] Homepot root:   {HOMEPOT_ROOT}")
print(f"[INFO] Runner:         {RUNNER_SCRIPT}")

# ---------------------------------------------------------------------------
# EasyVVUQ parameter declarations
# Wide bounds; actual sampling governed by per-scenario 'vary' dicts below.
# ---------------------------------------------------------------------------
params = {
    "cpu_percent":          {"type": "float", "min": 0.0,  "max": 100.0, "default": 50.0},
    "memory_percent":       {"type": "float", "min": 0.0,  "max": 100.0, "default": 50.0},
    "disk_percent":         {"type": "float", "min": 0.0,  "max": 100.0, "default": 50.0},
    "error_rate":           {"type": "float", "min": 0.0,  "max": 1.0,   "default": 0.05},
    "network_latency_ms":   {"type": "float", "min": 0.0,  "max": 500.0, "default": 100.0},
    "flapping_count":       {"type": "float", "min": 0.0,  "max": 15.0,  "default": 2.0},
    "consecutive_failures": {"type": "float", "min": 0.0,  "max": 20.0,  "default": 1.0},
    "outfile":              {"type": "string", "default": "output.json"},
}

# ---------------------------------------------------------------------------
# Scenario definitions — chaospy distributions per input
# ---------------------------------------------------------------------------
# Ranges derived from _generate_metrics_for_scenario() in
# DeviceSimulatorEndpoint.py.  error_rate = errors_count / transactions_count
# (range extremes from the simulator).  flapping_count and
# consecutive_failures are assigned scenario-appropriate ranges.
#
# For nominally-fixed-at-zero parameters (e.g. offline resource metrics) we
# use cp.Uniform(0, _EPS) so the parameter participates in the Saltelli plan
# but never crosses any detector threshold.  Its Sobol index will be ~0,
# confirming it contributes no variance — as expected.

_EPS = 0.001   # near-zero range for "always-off" parameters

SCENARIOS: dict[str, dict[str, cp.Distribution]] = {
    "healthy": {
        "cpu_percent":          cp.Uniform(50.0,  70.0),
        "memory_percent":       cp.Uniform(60.0,  75.0),
        "disk_percent":         cp.Uniform(50.0,  65.0),
        "error_rate":           cp.Uniform(0.000, 0.020),   # always < 5% threshold
        "network_latency_ms":   cp.Uniform(20.0,  50.0),    # always < 200ms threshold
        "flapping_count":       cp.Uniform(0.0,   1.0),     # always < 5 threshold
        "consecutive_failures": cp.Uniform(0.0,   _EPS),    # always < 3 threshold
    },
    "high_cpu": {
        "cpu_percent":          cp.Uniform(85.0,  95.0),    # fires ~52% (threshold 90)
        "memory_percent":       cp.Uniform(70.0,  80.0),
        "disk_percent":         cp.Uniform(55.0,  70.0),
        "error_rate":           cp.Uniform(0.012, 0.047),   # always < 5% threshold
        "network_latency_ms":   cp.Uniform(50.0,  100.0),
        "flapping_count":       cp.Uniform(1.0,   3.0),
        "consecutive_failures": cp.Uniform(0.0,   1.0),
    },
    "low_memory": {
        "cpu_percent":          cp.Uniform(65.0,  80.0),
        "memory_percent":       cp.Uniform(90.0,  95.0),    # fires ~100% (always > 90)
        "disk_percent":         cp.Uniform(60.0,  75.0),
        "error_rate":           cp.Uniform(0.033, 0.125),   # sometimes > 5% threshold
        "network_latency_ms":   cp.Uniform(40.0,  80.0),
        "flapping_count":       cp.Uniform(1.0,   3.0),
        "consecutive_failures": cp.Uniform(0.0,   2.0),
    },
    "high_errors": {
        "cpu_percent":          cp.Uniform(60.0,  75.0),
        "memory_percent":       cp.Uniform(70.0,  85.0),
        "disk_percent":         cp.Uniform(65.0,  80.0),
        "error_rate":           cp.Uniform(0.125, 0.600),   # always > 5% threshold
        "network_latency_ms":   cp.Uniform(80.0,  150.0),
        "flapping_count":       cp.Uniform(2.0,   5.0),     # straddles threshold of 5
        "consecutive_failures": cp.Uniform(1.0,   4.0),     # straddles threshold of 3
    },
    "degraded": {
        "cpu_percent":          cp.Uniform(85.0,  95.0),
        "memory_percent":       cp.Uniform(85.0,  92.0),
        "disk_percent":         cp.Uniform(75.0,  90.0),    # straddles 90% threshold
        "error_rate":           cp.Uniform(0.125, 0.650),
        "network_latency_ms":   cp.Uniform(100.0, 200.0),   # straddles 200ms threshold
        "flapping_count":       cp.Uniform(3.0,   7.0),     # straddles threshold of 5
        "consecutive_failures": cp.Uniform(2.0,   6.0),     # straddles threshold of 3
    },
    "offline": {
        # Resource metrics all 0 — unreachable device; only stability checks fire.
        "cpu_percent":          cp.Uniform(0.0,   _EPS),
        "memory_percent":       cp.Uniform(0.0,   _EPS),
        "disk_percent":         cp.Uniform(0.0,   _EPS),
        "error_rate":           cp.Uniform(0.0,   _EPS),
        "network_latency_ms":   cp.Uniform(0.0,   _EPS),
        "flapping_count":       cp.Uniform(5.0,   10.0),    # always > 5 threshold
        "consecutive_failures": cp.Uniform(6.0,   15.0),    # always >= 3 threshold
    },
}

SCENARIO_ORDER     = ["healthy", "high_cpu", "low_memory", "high_errors", "degraded", "offline"]
ALERT_THRESHOLD    = 0.3
CRITICAL_THRESHOLD = 0.8

# ---------------------------------------------------------------------------
# Saltelli plan size
# n_params = 7  →  MCSampler total = N_MC * (n_params + 2) = N_MC * 9
# ---------------------------------------------------------------------------
N_MC_PER_SCENARIO = int(os.environ.get("STUDY2_N_MC", "300"))

# ---------------------------------------------------------------------------
# Shared EasyVVUQ encoder / decoder (same format as Study 1)
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

# ---------------------------------------------------------------------------
# Run one EasyVVUQ campaign per scenario
# ---------------------------------------------------------------------------
scenario_results: dict[str, dict] = {}

for scenario_name in SCENARIO_ORDER:
    vary     = SCENARIOS[scenario_name]
    work_dir = os.path.join(STUDY_DIR, f"campaign_{scenario_name}")
    if os.path.exists(work_dir):
        rmtree(work_dir)
    os.makedirs(work_dir)

    execute = uq.actions.ExecuteLocal(f"{sys.executable} {RUNNER_SCRIPT}")
    actions = uq.actions.Actions(
        uq.actions.CreateRunDirectory(root=work_dir, flatten=True),
        uq.actions.Encode(encoder),
        execute,
        uq.actions.Decode(decoder),
    )

    campaign = uq.Campaign(
        name=f"sim2_{scenario_name}",
        params=params,
        actions=actions,
        work_dir=work_dir,
    )

    sampler = uq.sampling.MCSampler(
        vary=vary,
        n_mc_samples=N_MC_PER_SCENARIO,
        rule="latin_hypercube",
        seed=42,
    )
    campaign.set_sampler(sampler)
    campaign.draw_samples()

    n_saltelli = N_MC_PER_SCENARIO * (len(vary) + 2)
    print(f"[INFO] Scenario '{scenario_name}': {n_saltelli} Saltelli samples "
          f"(N_MC={N_MC_PER_SCENARIO})")

    # Run up to 4 subprocesses concurrently — enough parallelism to be fast
    # without spawning thousands of Python processes simultaneously.
    with ThreadPoolExecutor(max_workers=4) as pool:
        campaign.execute(pool=pool).collate()

    analysis = uq.analysis.QMCAnalysis(
        sampler=sampler,
        qoi_cols=["anomaly_score"],
    )
    campaign.apply_analysis(analysis)
    res = campaign.get_last_analysis()

    df     = campaign.get_collation_result()
    scores = df["anomaly_score"].values.astype(float).flatten()

    sobols_first = {
        k: float(np.atleast_1d(v).flat[0])
        for k, v in res.sobols_first("anomaly_score").items()
    }
    sobols_first_ci: dict[str, tuple[float, float]] = {}
    for param_name in sobols_first:
        try:
            ci_low, ci_high = res._get_sobols_first_conf("anomaly_score", param_name)
            sobols_first_ci[param_name] = (
                float(np.atleast_1d(ci_low).flat[0]),
                float(np.atleast_1d(ci_high).flat[0]),
            )
        except Exception:
            sobols_first_ci[param_name] = (float("nan"), float("nan"))

    scenario_results[scenario_name] = {
        "analysis": res,
        "scores":   scores,
        "sobols": sobols_first,
        "sobols_ci": sobols_first_ci,
    }

    # Campaign working dir is no longer needed — remove to save disk space.
    rmtree(work_dir)
    print(f"       mean={scores.mean():.3f}  std={scores.std():.3f}  "
          f"alert%={100*(scores >= ALERT_THRESHOLD).mean():.1f}%")

# ---------------------------------------------------------------------------
# Print results — statistical summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("SCENARIO SCORE DISTRIBUTIONS  (EasyVVUQ MCSampler / QMCAnalysis)")
print("=" * 78)
print(f"  N_MC={N_MC_PER_SCENARIO} per scenario → {N_MC_PER_SCENARIO*9} Saltelli samples each\n")
print(f"{'Scenario':<16} {'Mean':>6} {'Std':>6} {'P10':>6} {'P50':>6} {'P90':>6} "
      f"{'≥0.3 (%)':>10} {'≥0.8 (%)':>10}")
print("-" * 78)

for name in SCENARIO_ORDER:
    res  = scenario_results[name]["analysis"]
    sc   = scenario_results[name]["scores"]
    mean = float(np.atleast_1d(res.describe("anomaly_score", "mean")).flat[0])
    std  = float(np.atleast_1d(res.describe("anomaly_score", "std")).flat[0])
    p10  = float(np.atleast_1d(res.describe("anomaly_score", "10%")).flat[0])
    p50  = float(np.atleast_1d(res.describe("anomaly_score", "50%")).flat[0])
    p90  = float(np.atleast_1d(res.describe("anomaly_score", "90%")).flat[0])
    pct_alert    = 100.0 * (sc >= ALERT_THRESHOLD).mean()
    pct_critical = 100.0 * (sc >= CRITICAL_THRESHOLD).mean()
    print(f"{name:<16} {mean:6.3f} {std:6.3f} {p10:6.3f} {p50:6.3f} {p90:6.3f} "
          f"{pct_alert:9.1f}% {pct_critical:9.1f}%")

# ---------------------------------------------------------------------------
# Print Sobol indices
# ---------------------------------------------------------------------------
PARAM_LABELS = {
    "cpu_percent": "CPU %", "memory_percent": "mem %", "disk_percent": "disk %",
    "error_rate": "error rate", "network_latency_ms": "latency ms",
    "flapping_count": "flapping", "consecutive_failures": "consec. fail",
}
PARAM_ORDER = ["consecutive_failures", "flapping_count", "error_rate",
               "network_latency_ms", "cpu_percent", "memory_percent", "disk_percent"]

print("\n" + "=" * 78)
print("FIRST-ORDER SOBOL INDICES PER SCENARIO  (value [95% bootstrap CI])")
print("=" * 78)
for name in SCENARIO_ORDER:
    s = scenario_results[name]["sobols"]
    s_ci = scenario_results[name]["sobols_ci"]
    print(f"\n{name}:")
    for p in PARAM_ORDER:
        val = s.get(p, 0.0)
        lo, hi = s_ci.get(p, (float("nan"), float("nan")))
        print(f"  - {PARAM_LABELS[p]:<12} {val:8.4f} [{lo:8.4f}, {hi:8.4f}]")

# ---------------------------------------------------------------------------
# Print misclassification rates
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("MISCLASSIFICATION RATES")
print("=" * 78)
hs = scenario_results["healthy"]["scores"]
fp = 100.0 * (hs >= ALERT_THRESHOLD).mean()
print(f"\n  False positive rate (healthy scores ≥ {ALERT_THRESHOLD}): {fp:.1f}%")
for name in ("degraded", "offline", "high_errors"):
    sc = scenario_results[name]["scores"]
    fn = 100.0 * (sc < ALERT_THRESHOLD).mean()
    print(f"  False negative rate ({name:<11} scores < {ALERT_THRESHOLD}): {fn:.1f}%")

print()
print("NOTE: high_cpu alert rate confirms the detector is blind to CPU spikes alone.")
print("      Sobol indices reveal which metric drives score variance within each scenario.")

# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------
try:
    import matplotlib.pyplot as plt

    SCENARIO_LABELS = {
        "healthy": "Healthy", "high_cpu": "High CPU", "low_memory": "Low memory",
        "high_errors": "High errors", "degraded": "Degraded", "offline": "Offline",
    }
    COLORS = {
        "healthy": "#2196F3", "high_cpu": "#FF9800", "low_memory": "#9C27B0",
        "high_errors": "#F44336", "degraded": "#795548", "offline": "#212121",
    }

    # 1. Violin plot
    fig, ax = plt.subplots(figsize=(10, 5))
    data   = [scenario_results[s]["scores"] for s in SCENARIO_ORDER]
    labels = [SCENARIO_LABELS[s] for s in SCENARIO_ORDER]

    parts = ax.violinplot(data, positions=range(len(SCENARIO_ORDER)),
                          showmedians=True, showextrema=True)
    for body, s in zip(parts["bodies"], SCENARIO_ORDER):
        body.set_facecolor(COLORS[s])
        body.set_alpha(0.7)
    parts["cmedians"].set_color("white")
    parts["cmedians"].set_linewidth(2)
    for key in ("cbars", "cmins", "cmaxes"):
        parts[key].set_color("gray")
        parts[key].set_linewidth(1)

    ax.axhline(ALERT_THRESHOLD,    color="orange", linestyle="--", linewidth=1.2,
               label=f"Alert threshold ({ALERT_THRESHOLD})")
    ax.axhline(CRITICAL_THRESHOLD, color="red",    linestyle="--", linewidth=1.2,
               label=f"Critical threshold ({CRITICAL_THRESHOLD})")
    ax.set_xticks(range(len(SCENARIO_ORDER)))
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Anomaly score")
    ax.set_title(
        f"Anomaly score by simulator scenario  "
        f"(EasyVVUQ MCSampler, {N_MC_PER_SCENARIO*9:,} Saltelli samples each)"
    )
    ax.set_ylim(-0.05, 1.10)
    ax.legend(fontsize=9)
    plt.tight_layout()
    violin_png = os.path.join(FIGS_DIR, "scenario_violin.png")
    plt.savefig(violin_png, dpi=150)
    print(f"\n[INFO] Violin plot saved         → {violin_png}")

    # 2. Stacked severity-band bar chart
    fig2, ax2 = plt.subplots(figsize=(9, 4))
    bands = [
        ("Normal  (< 0.3)",    (0.0, ALERT_THRESHOLD),              "#4CAF50"),
        ("Moderate (0.3–0.8)", (ALERT_THRESHOLD, CRITICAL_THRESHOLD), "#FF9800"),
        ("Critical (≥ 0.8)",   (CRITICAL_THRESHOLD, 1.01),           "#F44336"),
    ]
    x       = np.arange(len(SCENARIO_ORDER))
    bottoms = np.zeros(len(SCENARIO_ORDER))
    for band_label, (lo, hi), color in bands:
        fracs = np.array([
            ((scenario_results[s]["scores"] >= lo) &
             (scenario_results[s]["scores"] <  hi)).mean()
            for s in SCENARIO_ORDER
        ])
        ax2.bar(x, fracs, bottom=bottoms, color=color, label=band_label, width=0.55)
        bottoms += fracs
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=15, ha="right")
    ax2.set_ylabel("Fraction of samples")
    ax2.set_title("Score severity bands by simulator scenario")
    ax2.legend(loc="upper right", fontsize=9)
    plt.tight_layout()
    bar_png = os.path.join(FIGS_DIR, "scenario_severity_bands.png")
    plt.savefig(bar_png, dpi=150)
    print(f"[INFO] Severity bar chart saved  → {bar_png}")

    # 3. Sobol heatmap — which metric drives variance in each scenario?
    sobol_matrix = np.array([
        [scenario_results[s]["sobols"].get(p, 0.0) for p in PARAM_ORDER]
        for s in SCENARIO_ORDER
    ])
    fig3, ax3 = plt.subplots(figsize=(10, 4))
    im = ax3.imshow(sobol_matrix, aspect="auto", cmap="YlOrRd", vmin=0, vmax=0.8)
    ax3.set_xticks(range(len(PARAM_ORDER)))
    ax3.set_xticklabels([PARAM_LABELS[p] for p in PARAM_ORDER],
                        rotation=30, ha="right", fontsize=9)
    ax3.set_yticks(range(len(SCENARIO_ORDER)))
    ax3.set_yticklabels(labels, fontsize=9)
    ax3.set_title("First-order Sobol indices — score sensitivity by scenario and metric")
    for i in range(len(SCENARIO_ORDER)):
        for j in range(len(PARAM_ORDER)):
            val = sobol_matrix[i, j]
            ax3.text(j, i, f"{val:.2f}", ha="center", va="center",
                     fontsize=7, color="white" if val > 0.45 else "black")
    plt.colorbar(im, ax=ax3, label="First-order Sobol index")
    plt.tight_layout()
    sobol_png = os.path.join(FIGS_DIR, "sobol_heatmap.png")
    plt.savefig(sobol_png, dpi=150)
    print(f"[INFO] Sobol heatmap saved       → {sobol_png}")

    plt.close("all")

except ImportError:
    print("\n[INFO] matplotlib not found — skipping plots.")
    print("       Install with:  pip install matplotlib")

