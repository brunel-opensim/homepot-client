"""Study 3: EasyVVUQ MCSampler / QMCAnalysis UQ for push notification reliability.

Uses the EasyVVUQ Saltelli sampling plan (``MCSampler``) and ``QMCAnalysis``
to quantify uncertainty in push notification delivery and compute first-order
Sobol sensitivity indices that identify which input (success rate or fleet
size) drives delivery variance.

Model (deterministic expected-value runner)
--------------------------------------------
Let  p = success_rate  ~ Beta(19, 1)           mean=0.95, weakly-informative
     n = num_devices   ~ DiscreteUniform(1, 50) values 1–50  (inclusive)

  expected_failures  = n * (1 - p)
  failure_rate       = 1 - p
  campaign_time_ms   = 100 + 400 * n / (n + 1)   (saturation model)

The runner (``push_runner.py``) is deterministic so that QMCAnalysis can
decompose variance via Sobol indices.  P(at least k succeed) is computed
post-collation from scipy.stats.binom.cdf applied to the collated samples.

EasyVVUQ Saltelli plan
-----------------------
  2 inputs → MCSampler total = N_MC * (n_params + 2) = N_MC * 4
  N_MC = 5 000 → 20 000 samples

Sensitivity analysis (lightweight campaigns)
---------------------------------------------
Three additional campaigns (N_MC = 1000 each) run with different Beta priors
to show how the prior assumption about success_rate affects the Sobol
decomposition and delivery statistics.

Run
---
    HOMEPOT_PATH=$(pwd) .venv/bin/python uq/study3_push/run_push_uq.py

Results are printed to stdout.  Four plots are saved to
``uq/study3_push/figs/``.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from shutil import rmtree

import scipy.special
# chaospy 4.3.2 still calls scipy.special.btdtri which was removed in scipy ≥ 1.14.
# Alias to the replacement so the rest of the stack works unchanged.
if not hasattr(scipy.special, "btdtri"):
    scipy.special.btdtri = scipy.special.betaincinv  # type: ignore[attr-defined]

import chaospy as cp
import easyvvuq as uq
import numpy as np
import scipy.stats as spstats

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
STUDY_DIR    = os.path.dirname(os.path.abspath(__file__))
HOMEPOT_ROOT = os.environ.get(
    "HOMEPOT_PATH",
    os.path.abspath(os.path.join(STUDY_DIR, "../..")),
)
FIGS_DIR = os.path.join(STUDY_DIR, "figs")
os.makedirs(FIGS_DIR, exist_ok=True)

RUNNER_SCRIPT  = os.path.join(STUDY_DIR, "push_runner.py")
TEMPLATE_FILE  = os.path.join(STUDY_DIR, "push_runner.template")

os.environ.setdefault("HOMEPOT_PATH", HOMEPOT_ROOT)
print(f"[INFO] Homepot root: {HOMEPOT_ROOT}")

# ---------------------------------------------------------------------------
# EasyVVUQ parameter spec (must cover every template variable incl. outfile)
# ---------------------------------------------------------------------------
params = {
    "success_rate": {"type": "float", "default": 0.95, "min": 0.0, "max": 1.0},
    "num_devices":  {"type": "float", "default": 25.0, "min": 1.0, "max": 50.0},
    "outfile":      {"type": "string", "default": "output.json"},
}

QOI_COLS = ["expected_failures", "failure_rate", "campaign_time_ms"]

N_MC_MAIN = 5_000   # → 20 000 Saltelli samples (2 params → *4)

# ---------------------------------------------------------------------------
# Shared encoder / decoder
# ---------------------------------------------------------------------------
encoder = uq.encoders.GenericEncoder(
    template_fname=TEMPLATE_FILE,
    delimiter="$",
    target_filename="input.json",
)
decoder = uq.decoders.JSONDecoder(
    target_filename="output.json",
    output_columns=QOI_COLS,
)

# ---------------------------------------------------------------------------
# Helper: run one EasyVVUQ campaign and return (analysis, collation_df)
# ---------------------------------------------------------------------------

def run_campaign(vary: dict, n_mc: int, seed: int, name: str):
    work_dir = os.path.join(STUDY_DIR, f"campaign_{name}")
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
        name=name,
        params=params,
        actions=actions,
        work_dir=work_dir,
    )

    sampler = uq.sampling.MCSampler(
        vary=vary,
        n_mc_samples=n_mc,
        rule="latin_hypercube",
        seed=seed,
    )
    campaign.set_sampler(sampler)
    campaign.draw_samples()

    n_total = n_mc * (len(vary) + 2)
    print(f"[INFO] Campaign '{name}': {n_total:,} Saltelli samples "
          f"(N_MC={n_mc}, {len(vary)} inputs)")

    with ThreadPoolExecutor(max_workers=4) as pool:
        campaign.execute(pool=pool).collate()

    analysis = uq.analysis.QMCAnalysis(sampler=sampler, qoi_cols=QOI_COLS)
    campaign.apply_analysis(analysis)
    res = campaign.get_last_analysis()
    df  = campaign.get_collation_result()

    rmtree(work_dir)
    return res, df


# ---------------------------------------------------------------------------
# Main campaign — nominal priors
# ---------------------------------------------------------------------------
VARY_NOMINAL = {
    "success_rate": cp.Beta(19.0, 1.0),          # mean = 0.95
    "num_devices":  cp.DiscreteUniform(1, 50),    # integers 1–50 inclusive
}

res_main, df_main = run_campaign(VARY_NOMINAL, N_MC_MAIN, seed=0, name="push3_nominal")

scores_ef   = df_main["expected_failures"].values.astype(float)
scores_fr   = df_main["failure_rate"].values.astype(float)
scores_time = df_main["campaign_time_ms"].values.astype(float)

# ---------------------------------------------------------------------------
# Print main campaign results
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("MAIN CAMPAIGN RESULTS  (EasyVVUQ MCSampler, nominal priors)")
print("=" * 72)
print(f"  N_MC={N_MC_MAIN} → {N_MC_MAIN*4:,} Saltelli samples\n")

for qoi, arr, unit in [
    ("expected_failures",  scores_ef,   "devices"),
    ("failure_rate",       scores_fr,   "fraction"),
    ("campaign_time_ms",   scores_time, "ms"),
]:
    mean = float(np.atleast_1d(res_main.describe(qoi, "mean")).flat[0])
    std  = float(np.atleast_1d(res_main.describe(qoi, "std")).flat[0])
    p10  = float(np.atleast_1d(res_main.describe(qoi, "10%")).flat[0])
    p90  = float(np.atleast_1d(res_main.describe(qoi, "90%")).flat[0])
    print(f"  {qoi:<22}  mean={mean:8.4f}  std={std:7.4f}  "
          f"[P10={p10:.4f}, P90={p90:.4f}]  ({unit})")

# ── Sobol indices ───────────────────────────────────────────────────────────
print("\n" + "-" * 72)
print("  First-order Sobol indices — fraction of QoI variance")
print(f"  {'QoI':<22}  {'success_rate':>14}  {'num_devices':>12}")
print("  " + "-" * 52)
for qoi in QOI_COLS:
    s1 = res_main.sobols_first(qoi)
    sr = float(np.atleast_1d(s1.get("success_rate", 0.0)).flat[0])
    nd = float(np.atleast_1d(s1.get("num_devices",  0.0)).flat[0])
    print(f"  {qoi:<22}  {sr:14.4f}  {nd:12.4f}")

# ---------------------------------------------------------------------------
# Post-collation P(at least k succeed) for a campaign of N=50 devices
# ---------------------------------------------------------------------------
N_FIXED = 50
# Filter collated samples with num_devices == 50 (exact match after int rounding)
nd_vals = df_main["num_devices"].values.astype(float).round().astype(int)
mask50  = (nd_vals == N_FIXED)
p_arr   = 1.0 - df_main.loc[mask50, "failure_rate"].values.astype(float)

if p_arr.size > 0:
    k_values    = np.arange(N_FIXED - 10, N_FIXED + 1)
    p_at_least_k = np.array([
        spstats.binom.cdf(N_FIXED - k, N_FIXED, 1.0 - p_arr.mean()).item()
        for k in k_values
    ])
    print("\n" + "=" * 72)
    print(f"P(at least k of {N_FIXED} devices succeed) — mean success_rate from "
          f"n=50 subsample ({mask50.sum()} samples)")
    print("=" * 72)
    print(f"  {'k':>5}   {'P(≥k)':>8}")
    print("  " + "-" * 18)
    for k, p in zip(k_values, p_at_least_k):
        bar = "█" * int(round(p * 20))
        print(f"  {k:>5}   {p:8.4f}  {bar}")
else:
    k_values     = np.array([])
    p_at_least_k = np.array([])
    print("[WARN] No samples with num_devices == 50 in main collation.")

# ---------------------------------------------------------------------------
# Sensitivity campaigns — three Beta priors
# ---------------------------------------------------------------------------
SENSITIVITY_SCENARIOS = {
    "optimistic_beta95_5":  ("Optimistic  Beta(95,5)",  cp.Beta(95.0, 5.0)),
    "nominal_beta19_1":     ("Nominal     Beta(19,1)",  cp.Beta(19.0, 1.0)),
    "pessimistic_beta9_1":  ("Pessimistic Beta(9,1)",   cp.Beta(9.0,  1.0)),
}
N_MC_SENSITIVITY = 1_000

sens_results = {}
for key, (label, prior) in SENSITIVITY_SCENARIOS.items():
    vary_s = {
        "success_rate": prior,
        "num_devices":  cp.DiscreteUniform(1, 50),
    }
    r_s, df_s = run_campaign(vary_s, N_MC_SENSITIVITY, seed=7, name=f"push3_{key}")
    sens_results[key] = {
        "label": label,
        "analysis": r_s,
        "df": df_s,
    }

# ── Print sensitivity results ───────────────────────────────────────────────
print("\n" + "=" * 72)
print("SENSITIVITY TO success_rate PRIOR  (n ~ DiscreteUniform(1,50))")
print("=" * 72)
print(f"\n  {'Prior':<32} {'E[fail rate]':>12} {'P10':>8} {'P90':>8} "
      f"{'S1(p)':>8} {'S1(n)':>8}")
print("  " + "-" * 80)
for key, sr in sens_results.items():
    r      = sr["analysis"]
    label  = sr["label"]
    mean   = float(np.atleast_1d(r.describe("failure_rate", "mean")).flat[0])
    p10    = float(np.atleast_1d(r.describe("failure_rate", "10%")).flat[0])
    p90    = float(np.atleast_1d(r.describe("failure_rate", "90%")).flat[0])
    s1     = r.sobols_first("failure_rate")
    s1_p   = float(np.atleast_1d(s1.get("success_rate", 0.0)).flat[0])
    s1_n   = float(np.atleast_1d(s1.get("num_devices",  0.0)).flat[0])
    print(f"  {label:<32} {mean:12.4f} {p10:8.4f} {p90:8.4f} {s1_p:8.4f} {s1_n:8.4f}")

# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------
try:
    import matplotlib.pyplot as plt

    # 1. failure_rate histogram (main campaign)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(scores_fr, bins=60, color="steelblue", edgecolor="white", density=True)
    ax.set_xlabel("Per-device failure rate  (1 − success_rate)")
    ax.set_ylabel("Probability density")
    ax.set_title(
        "Distribution of failure rate\n"
        f"(n ~ DiscreteUniform(1,50), p ~ Beta(19,1), "
        f"N_MC={N_MC_MAIN:,})"
    )
    plt.tight_layout()
    png1 = os.path.join(FIGS_DIR, "failure_rate_hist.png")
    plt.savefig(png1, dpi=150)
    print(f"\n[INFO] Failure rate histogram saved  → {png1}")

    # 2. P(at least k succeed) for n=50
    if k_values.size > 0:
        fig2, ax2 = plt.subplots(figsize=(8, 4))
        ax2.bar(k_values, p_at_least_k, color="steelblue", width=0.6)
        ax2.set_xlabel("Minimum successes required (k)")
        ax2.set_ylabel("Probability")
        ax2.set_title(
            f"P(at least k of {N_FIXED} devices receive notification)\n"
            f"p ~ Beta(19,1), mean success rate from {mask50.sum()} collated samples"
        )
        ax2.set_ylim(0, 1.10)
        ax2.set_xticks(k_values)
        for k, p in zip(k_values, p_at_least_k):
            ax2.text(k, p + 0.015, f"{p:.3f}", ha="center", va="bottom", fontsize=8)
        plt.tight_layout()
        png2 = os.path.join(FIGS_DIR, "p_at_least_k.png")
        plt.savefig(png2, dpi=150)
        print(f"[INFO] P(at least k) chart saved     → {png2}")

    # 3. Delivery confidence vs fleet size (using campaign_time saturation curve)
    n_arr    = df_main["num_devices"].values.astype(float).round().astype(int)
    time_arr = df_main["campaign_time_ms"].values.astype(float)
    fleet_sizes = np.arange(1, 51)
    mean_time_by_n = np.array([
        time_arr[n_arr == n].mean() if (n_arr == n).any()
        else (100.0 + 400.0 * n / (n + 1.0))
        for n in fleet_sizes
    ])
    p_zero_fail = np.array([
        (df_main.loc[n_arr == n, "expected_failures"].values.astype(float) < 1.0).mean()
        if (n_arr == n).any() else np.nan
        for n in fleet_sizes
    ])

    fig3, ax3a = plt.subplots(figsize=(9, 4))
    ax3b = ax3a.twinx()
    ax3a.plot(fleet_sizes, mean_time_by_n, color="steelblue",
              label="Mean campaign time (ms)")
    ax3b.plot(fleet_sizes, p_zero_fail * 100, color="darkorange", linestyle="--",
              label="P(expected failures < 1) %")
    ax3a.set_xlabel("Fleet / campaign size  n")
    ax3a.set_ylabel("Campaign time (ms)", color="steelblue")
    ax3b.set_ylabel("P(expected_failures < 1)  %", color="darkorange")
    ax3a.set_title("Campaign time and zero-failure probability vs fleet size")
    lines_a, labels_a = ax3a.get_legend_handles_labels()
    lines_b, labels_b = ax3b.get_legend_handles_labels()
    ax3a.legend(lines_a + lines_b, labels_a + labels_b, fontsize=9, loc="center right")
    plt.tight_layout()
    png3 = os.path.join(FIGS_DIR, "confidence_vs_fleet_size.png")
    plt.savefig(png3, dpi=150)
    print(f"[INFO] Confidence vs fleet size saved → {png3}")

    # 4. Sensitivity: failure_rate distributions for different priors
    senscols = {
        "optimistic_beta95_5": "#4CAF50",
        "nominal_beta19_1":    "#2196F3",
        "pessimistic_beta9_1": "#F44336",
    }
    fig4, ax4 = plt.subplots(figsize=(9, 4))
    bins = np.linspace(0.0, 0.25, 50)
    for key, color in senscols.items():
        label = sens_results[key]["label"].strip()
        fr    = sens_results[key]["df"]["failure_rate"].values.astype(float)
        ax4.hist(fr, bins=bins, alpha=0.55, color=color, density=True, label=label)
    ax4.set_xlabel("Per-device failure rate")
    ax4.set_ylabel("Probability density")
    ax4.set_title("Sensitivity to success_rate assumption\n"
                  f"(n ~ DiscreteUniform(1,50), N_MC={N_MC_SENSITIVITY:,} each)")
    ax4.legend(fontsize=9)
    plt.tight_layout()
    png4 = os.path.join(FIGS_DIR, "failure_sensitivity.png")
    plt.savefig(png4, dpi=150)
    print(f"[INFO] Failure sensitivity chart saved → {png4}")

    plt.close("all")

except ImportError:
    print("\n[INFO] matplotlib not found — skipping plots.")
    print("       Install with:  pip install matplotlib")

