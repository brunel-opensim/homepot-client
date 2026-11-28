"""Study 4: Extended anomaly detector sensitivity (EasyVVUQ MCSampler / QMCAnalysis).

Extends Study 2's scenario boundary validation to the detector's full input
set, including the device-health signals added in PR #1099 (battery,
temperature, CPU speed, Wi-Fi signal strength).  For each of the six
device-simulator scenarios, an EasyVVUQ campaign is run with the Saltelli-plan
``MCSampler``.  ``QMCAnalysis`` then computes first- and total-order Sobol
sensitivity indices showing which input metric drives score variance most within
each scenario.

Sampling plan
-------------
``MCSampler`` uses a Saltelli plan: total samples per scenario is
``N_MC_PER_SCENARIO × (n_params + 2) = N_MC_PER_SCENARIO × 11``.  With
``N_MC_PER_SCENARIO = 300`` each scenario gets **3 300 samples**.  Six
scenarios → **19 800 model evaluations** total.

Run
---
    # From the homepot-client root:
    HOMEPOT_PATH=$(pwd) .venv/bin/python uq/study4_extended/run_extended_uq.py

Output is printed to stdout.  Three plots are saved to
``uq/study4_extended/figs/``.  Campaign working directories are removed
automatically after each scenario's analysis completes.
"""

from concurrent.futures import ThreadPoolExecutor
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
        "    .venv/bin/pip install -e /path/to/EasyVVUQ\n",
        file=sys.stderr,
    )
    raise exc

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
STUDY_DIR = os.path.dirname(os.path.abspath(__file__))
HOMEPOT_ROOT = os.environ.get(
    "HOMEPOT_PATH",
    os.path.abspath(os.path.join(STUDY_DIR, "../..")),
)
FIGS_DIR = os.path.join(STUDY_DIR, "figs")
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
    "cpu_percent": {"type": "float", "min": 0.0, "max": 100.0, "default": 50.0},
    "memory_percent": {"type": "float", "min": 0.0, "max": 100.0, "default": 50.0},
    "disk_percent": {"type": "float", "min": 0.0, "max": 100.0, "default": 50.0},
    "error_rate": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.05},
    "network_latency_ms": {"type": "float", "min": 0.0, "max": 500.0, "default": 100.0},
    "flapping_count": {"type": "float", "min": 0.0, "max": 15.0, "default": 2.0},
    "consecutive_failures": {"type": "float", "min": 0.0, "max": 20.0, "default": 1.0},
    "battery_percent": {"type": "float", "min": 0.0, "max": 100.0, "default": 80.0},
    "cpu_temp_c": {"type": "float", "min": 0.0, "max": 100.0, "default": 50.0},
    "cpu_speed_mhz": {"type": "float", "min": 0.0, "max": 3000.0, "default": 2000.0},
    "cpu_speed_max_mhz": {
        "type": "float",
        "min": 100.0,
        "max": 4000.0,
        "default": 2400.0,
    },
    "wifi_signal_dbm": {"type": "float", "min": -100.0, "max": -20.0, "default": -50.0},
    "outfile": {"type": "string", "default": "output.json"},
}

# ---------------------------------------------------------------------------
# Scenario definitions — chaospy distributions per input
# ---------------------------------------------------------------------------
# Ranges derived from _generate_metrics_for_scenario() in
# DeviceSimulatorEndpoint.py for the original seven metrics, plus scenario-
# appropriate ranges for the new device-health signals (battery, temperature,
# CPU speed, Wi-Fi RSSI) so that each scenario exercises both sides of the
# detector's new thresholds.
#
# For nominally-fixed-at-zero parameters (e.g. offline resource metrics) we
# use cp.Uniform(0, _EPS) so the parameter participates in the Saltelli plan
# but never crosses any detector threshold.  Its Sobol index will be ~0,
# confirming it contributes no variance — as expected.

_EPS = 0.001  # near-zero range for "always-off" parameters

SCENARIOS: dict[str, dict[str, cp.Distribution]] = {
    "healthy": {
        "cpu_percent": cp.Uniform(50.0, 70.0),
        "memory_percent": cp.Uniform(60.0, 75.0),
        "disk_percent": cp.Uniform(50.0, 65.0),
        "error_rate": cp.Uniform(0.000, 0.020),
        "network_latency_ms": cp.Uniform(20.0, 50.0),
        "flapping_count": cp.Uniform(0.0, 1.0),
        "consecutive_failures": cp.Uniform(0.0, _EPS),
        "battery_percent": cp.Uniform(80.0, 100.0),
        "cpu_temp_c": cp.Uniform(40.0, 60.0),
        "cpu_speed_mhz": cp.Uniform(2000.0, 2400.0),
        "wifi_signal_dbm": cp.Uniform(-50.0, -30.0),
    },
    "high_cpu": {
        "cpu_percent": cp.Uniform(85.0, 95.0),
        "memory_percent": cp.Uniform(70.0, 80.0),
        "disk_percent": cp.Uniform(55.0, 70.0),
        "error_rate": cp.Uniform(0.012, 0.047),
        "network_latency_ms": cp.Uniform(50.0, 100.0),
        "flapping_count": cp.Uniform(1.0, 3.0),
        "consecutive_failures": cp.Uniform(0.0, 1.0),
        "battery_percent": cp.Uniform(60.0, 85.0),
        "cpu_temp_c": cp.Uniform(70.0, 85.0),
        "cpu_speed_mhz": cp.Uniform(1800.0, 2300.0),
        "wifi_signal_dbm": cp.Uniform(-55.0, -40.0),
    },
    "low_memory": {
        "cpu_percent": cp.Uniform(65.0, 80.0),
        "memory_percent": cp.Uniform(90.0, 95.0),
        "disk_percent": cp.Uniform(60.0, 75.0),
        "error_rate": cp.Uniform(0.033, 0.125),
        "network_latency_ms": cp.Uniform(40.0, 80.0),
        "flapping_count": cp.Uniform(1.0, 3.0),
        "consecutive_failures": cp.Uniform(0.0, 2.0),
        "battery_percent": cp.Uniform(50.0, 75.0),
        "cpu_temp_c": cp.Uniform(55.0, 70.0),
        "cpu_speed_mhz": cp.Uniform(1900.0, 2300.0),
        "wifi_signal_dbm": cp.Uniform(-60.0, -45.0),
    },
    "high_errors": {
        "cpu_percent": cp.Uniform(60.0, 75.0),
        "memory_percent": cp.Uniform(70.0, 85.0),
        "disk_percent": cp.Uniform(65.0, 80.0),
        "error_rate": cp.Uniform(0.125, 0.600),
        "network_latency_ms": cp.Uniform(80.0, 150.0),
        "flapping_count": cp.Uniform(2.0, 5.0),
        "consecutive_failures": cp.Uniform(1.0, 4.0),
        "battery_percent": cp.Uniform(40.0, 70.0),
        "cpu_temp_c": cp.Uniform(60.0, 75.0),
        "cpu_speed_mhz": cp.Uniform(1700.0, 2200.0),
        "wifi_signal_dbm": cp.Uniform(-70.0, -50.0),
    },
    "degraded": {
        "cpu_percent": cp.Uniform(85.0, 95.0),
        "memory_percent": cp.Uniform(85.0, 92.0),
        "disk_percent": cp.Uniform(75.0, 90.0),
        "error_rate": cp.Uniform(0.125, 0.650),
        "network_latency_ms": cp.Uniform(100.0, 200.0),
        "flapping_count": cp.Uniform(3.0, 7.0),
        "consecutive_failures": cp.Uniform(2.0, 6.0),
        "battery_percent": cp.Uniform(10.0, 50.0),
        "cpu_temp_c": cp.Uniform(80.0, 95.0),
        "cpu_speed_mhz": cp.Uniform(800.0, 1400.0),
        "wifi_signal_dbm": cp.Uniform(-90.0, -70.0),
    },
    "offline": {
        "cpu_percent": cp.Uniform(0.0, _EPS),
        "memory_percent": cp.Uniform(0.0, _EPS),
        "disk_percent": cp.Uniform(0.0, _EPS),
        "error_rate": cp.Uniform(0.0, _EPS),
        "network_latency_ms": cp.Uniform(0.0, _EPS),
        "flapping_count": cp.Uniform(5.0, 10.0),
        "consecutive_failures": cp.Uniform(6.0, 15.0),
        "battery_percent": cp.Uniform(0.0, _EPS),
        "cpu_temp_c": cp.Uniform(0.0, _EPS),
        "cpu_speed_mhz": cp.Uniform(0.0, _EPS),
        "wifi_signal_dbm": cp.Uniform(-100.0, -99.0),
    },
}

SCENARIO_ORDER = [
    "healthy",
    "high_cpu",
    "low_memory",
    "high_errors",
    "degraded",
    "offline",
]

ALERT_THRESHOLD = 0.3
CRITICAL_THRESHOLD = 0.8

# ---------------------------------------------------------------------------
# Saltelli plan size
# n_params = 11 (9 varied + 2 int) → Saltelli total = N_MC * (n_params + 2)
# ---------------------------------------------------------------------------
N_MC_PER_SCENARIO = int(os.environ.get("STUDY4_N_MC", "300"))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CAMPAIGN_WORK_DIR = os.path.join(STUDY_DIR, "campaign_extended")
FIGS_DIR = os.path.join(STUDY_DIR, "figs")
TEMPLATE_FILE = os.path.join(STUDY_DIR, "anomaly_runner.template")
RUNNER_SCRIPT = os.path.join(STUDY_DIR, "anomaly_runner.py")
os.makedirs(FIGS_DIR, exist_ok=True)

os.environ.setdefault("HOMEPOT_PATH", HOMEPOT_ROOT)

# ---------------------------------------------------------------------------
# Shared EasyVVUQ encoder / decoder (same format as Study 2)
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
execute = uq.actions.ExecuteLocal(f"{sys.executable} {RUNNER_SCRIPT}")
actions = uq.actions.Actions(
    uq.actions.CreateRunDirectory(root=CAMPAIGN_WORK_DIR, flatten=True),
    uq.actions.Encode(encoder),
    execute,
    uq.actions.Decode(decoder),
)

# ---------------------------------------------------------------------------
# Run one EasyVVUQ campaign per scenario
# ---------------------------------------------------------------------------
scenario_results: dict[str, dict] = {}

for scenario_name in SCENARIO_ORDER:
    vary = SCENARIOS[scenario_name]
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
        name=f"sim4_{scenario_name}",
        params=params,
        actions=actions,
        work_dir=work_dir,
    )

    sampler = uq.sampling.MCSampler(
        vary=vary,
        n_mc_samples=N_MC_PER_SCENARIO,
        rule="sobol",
        seed=42,
    )
    campaign.set_sampler(sampler)
    campaign.draw_samples()

    n_saltelli = N_MC_PER_SCENARIO * (len(vary) + 2)
    print(
        f"[INFO] Scenario '{scenario_name}': {n_saltelli} Saltelli samples "
        f"(N_MC={N_MC_PER_SCENARIO})"
    )

    with ThreadPoolExecutor(max_workers=4) as pool:
        campaign.execute(pool=pool).collate()

    analysis = uq.analysis.QMCAnalysis(
        sampler=sampler,
        qoi_cols=["anomaly_score"],
    )
    campaign.apply_analysis(analysis)
    res = campaign.get_last_analysis()

    df = campaign.get_collation_result()
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
        "scores": scores,
        "sobols": sobols_first,
        "sobols_ci": sobols_first_ci,
    }

    rmtree(work_dir)
    print(
        f"       mean={scores.mean():.3f}  std={scores.std():.3f}  "
        f"alert%={100 * (scores >= ALERT_THRESHOLD).mean():.1f}%"
    )

# ---------------------------------------------------------------------------
# Print results — statistical summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 90)
print("SCENARIO SCORE DISTRIBUTIONS  (EasyVVUQ MCSampler / QMCAnalysis)")
print("=" * 90)
print(
    f"  N_MC={N_MC_PER_SCENARIO} per scenario → {N_MC_PER_SCENARIO * 11} Saltelli samples each\n"
)

print(
    f"{'Scenario':<16} {'Mean':>6} {'Std':>6} {'P10':>6} {'P50':>6} {'P90':>6} "
    f"{'≥0.3 (%)':>10} {'≥0.8 (%)':>10}"
)
print("-" * 90)

for name in SCENARIO_ORDER:
    res = scenario_results[name]["analysis"]
    sc = scenario_results[name]["scores"]
    mean = float(np.atleast_1d(res.describe("anomaly_score", "mean")).flat[0])
    std = float(np.atleast_1d(res.describe("anomaly_score", "std")).flat[0])
    p10 = float(np.atleast_1d(res.describe("anomaly_score", "10%")).flat[0])
    p50 = float(np.atleast_1d(res.describe("anomaly_score", "50%")).flat[0])
    p90 = float(np.atleast_1d(res.describe("anomaly_score", "90%")).flat[0])
    pct_alert = 100.0 * (sc >= ALERT_THRESHOLD).mean()
    pct_critical = 100.0 * (sc >= CRITICAL_THRESHOLD).mean()
    print(
        f"{name:<16} {mean:6.3f} {std:6.3f} {p10:6.3f} {p50:6.3f} {p90:6.3f} "
        f"{pct_alert:9.1f}% {pct_critical:9.1f}%"
    )

# ---------------------------------------------------------------------------
# Print Sobol indices
# ---------------------------------------------------------------------------
PARAM_LABELS = {
    "consecutive_failures": "consec. fail",
    "flapping_count": "flapping",
    "error_rate": "error rate",
    "network_latency_ms": "latency ms",
    "cpu_percent": "CPU %",
    "memory_percent": "mem %",
    "disk_percent": "disk %",
    "battery_percent": "battery %",
    "cpu_temp_c": "CPU temp",
    "cpu_speed_mhz": "CPU MHz",
    "wifi_signal_dbm": "Wi-Fi dBm",
}

PARAM_ORDER = [
    "consecutive_failures",
    "flapping_count",
    "error_rate",
    "network_latency_ms",
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "battery_percent",
    "cpu_temp_c",
    "cpu_speed_mhz",
    "wifi_signal_dbm",
]

print("\n" + "=" * 90)
print("FIRST-ORDER SOBOL INDICES PER SCENARIO  (value [95% bootstrap CI])")
print("=" * 90)
for name in SCENARIO_ORDER:
    s = scenario_results[name]["sobols"]
    s_ci = scenario_results[name]["sobols_ci"]
    print(f"\n{name}:")
    for p in PARAM_ORDER:
        val = s.get(p, 0.0)
        lo, hi = s_ci.get(p, (float("nan"), float("nan")))
        print(f"  - {PARAM_LABELS[p]:<12} {val:8.4f} [{lo:8.4f}, {hi:8.4f}]")

print()
print("NOTE: high_cpu alert rate confirms the detector is blind to CPU spikes alone.")
print(
    "      Sobol indices reveal which metric drives score variance within each scenario."
)

# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------
try:
    import matplotlib.pyplot as plt

    SCENARIO_LABELS = {
        "healthy": "Healthy",
        "high_cpu": "High CPU",
        "low_memory": "Low memory",
        "high_errors": "High errors",
        "degraded": "Degraded",
        "offline": "Offline",
    }
    COLORS = {
        "healthy": "#2196F3",
        "high_cpu": "#FF9800",
        "low_memory": "#9C27B0",
        "high_errors": "#F44336",
        "degraded": "#795548",
        "offline": "#212121",
    }

    # 1. Violin plot
    fig, ax = plt.subplots(figsize=(12, 5))
    data = [scenario_results[s]["scores"] for s in SCENARIO_ORDER]
    labels = [SCENARIO_LABELS[s] for s in SCENARIO_ORDER]

    parts = ax.violinplot(
        data, positions=range(len(SCENARIO_ORDER)), showmedians=True, showextrema=True
    )
    for body, s in zip(parts["bodies"], SCENARIO_ORDER):  # type: ignore
        body.set_facecolor(COLORS[s])
        body.set_alpha(0.7)
    parts["cmedians"].set_color("white")
    parts["cmedians"].set_linewidth(2)
    for key in ("cbars", "cmins", "cmaxes"):
        parts[key].set_color("gray")
        parts[key].set_linewidth(1)

    ax.axhline(
        ALERT_THRESHOLD,
        color="orange",
        linestyle="--",
        linewidth=1.2,
        label=f"Alert threshold ({ALERT_THRESHOLD})",
    )
    ax.axhline(
        CRITICAL_THRESHOLD,
        color="red",
        linestyle="--",
        linewidth=1.2,
        label=f"Critical threshold ({CRITICAL_THRESHOLD})",
    )
    ax.set_xticks(range(len(SCENARIO_ORDER)))
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Anomaly score")
    ax.set_title(
        f"Anomaly score by simulator scenario  "
        f"(EasyVVUQ MCSampler, {N_MC_PER_SCENARIO * 11:,} Saltelli samples each)"
    )
    ax.set_ylim(-0.05, 1.10)
    ax.legend(fontsize=9)
    plt.tight_layout()
    violin_png = os.path.join(FIGS_DIR, "scenario_violin.png")
    plt.savefig(violin_png, dpi=150)
    print(f"\n[INFO] Violin plot saved         → {violin_png}")

    # 2. Sobol heatmap — which metric drives variance in each scenario?
    sobol_matrix = np.array(
        [
            [scenario_results[s]["sobols"].get(p, 0.0) for p in PARAM_ORDER]
            for s in SCENARIO_ORDER
        ]
    )
    fig3, ax3 = plt.subplots(figsize=(12, 5))
    im = ax3.imshow(sobol_matrix, aspect="auto", cmap="YlOrRd", vmin=0, vmax=0.8)
    ax3.set_xticks(range(len(PARAM_ORDER)))
    ax3.set_xticklabels(
        [PARAM_LABELS[p] for p in PARAM_ORDER], rotation=30, ha="right", fontsize=8
    )
    ax3.set_yticks(range(len(SCENARIO_ORDER)))
    ax3.set_yticklabels(labels, fontsize=9)
    ax3.set_title(
        "First-order Sobol indices — score sensitivity by scenario and metric"
    )
    for i in range(len(SCENARIO_ORDER)):
        for j in range(len(PARAM_ORDER)):
            val = sobol_matrix[i, j]
            ax3.text(
                j,
                i,
                f"{val:.2f}",
                ha="center",
                va="center",
                fontsize=7,
                color="white" if val > 0.45 else "black",
            )
    plt.colorbar(im, ax=ax3, label="First-order Sobol index")
    plt.tight_layout()
    sobol_png = os.path.join(FIGS_DIR, "sobol_heatmap.png")
    plt.savefig(sobol_png, dpi=150)
    print(f"[INFO] Sobol heatmap saved       → {sobol_png}")

    plt.close("all")

except ImportError:
    print("\n[INFO] matplotlib not found — skipping plots.")
    print("       Install with:  pip install matplotlib")
