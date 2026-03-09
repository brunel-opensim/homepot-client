# HOMEPOT-Client: VVUQ Overview

This directory applies **Verification, Validation and Uncertainty Quantification
(VVUQ)** to the HOMEPOT-Client codebase using
[EasyVVUQ](https://github.com/UCL-CCS/EasyVVUQ).

> **EasyVVUQ is not yet on PyPI.** Clone it from GitHub and install it in editable
> mode into the homepot venv (see [Setup](#setup) below).

---

## Table of Contents

1. [What is UQ and why does it matter here?](#what-is-uq-and-why-does-it-matter-here)
2. [Setup](#setup)
3. [Studies at a glance](#studies-at-a-glance)
4. [Directory structure](#directory-structure)

---

## What is UQ and why does it matter here?

### What is Uncertainty Quantification?

When a software system takes inputs and produces outputs, its behaviour is usually
tested at a small number of fixed, hand-picked input values. That is fine for checking
that specific cases work correctly, but it tells you nothing about how the system
**behaves across the full range of inputs it will realistically encounter in
production**.

**Uncertainty Quantification (UQ)** is the discipline of systematically exploring how
variability (or *uncertainty*) in the inputs of a model propagates through to
variability in the outputs. The key questions UQ answers are:

- **What is the distribution of the output?**  
  If inputs are not fixed but can take a range of values, what range of outputs should
  we expect? What is the most likely output? What are the extremes?

- **Which inputs matter most?**  
  If the output varies a lot, is that because of input A, or input B, or some
  combination? This is called **sensitivity analysis**. It identifies which parameters
  are the critical ones to monitor, control, or measure more precisely.

UQ is established practice in fields such as climate modelling, aerospace engineering,
and medical simulation — wherever decisions depend on computational models and it is
important to understand those models' behaviour under the full range of plausible
conditions, not just specific test cases.

### What is EasyVVUQ?

[EasyVVUQ](https://github.com/UCL-CCS/EasyVVUQ) is a Python library that provides a
simple, structured way to run UQ campaigns on any existing code. It was designed
specifically for cases where you have an existing model (a simulation, a scoring
function, an AI component) and want to understand its behaviour without rewriting it.

EasyVVUQ works by:
1. Generating many carefully-chosen input combinations (a **sample set**).
2. Running your model once for each combination.
3. Collecting all the outputs and performing statistical analysis.

### Why is UQ relevant to HOMEPOT?

HOMEPOT-Client includes an AI layer (`ai/`) that makes automated decisions about
device health and failure risk. Those decisions depend on scoring functions with
**manually chosen weights and thresholds**. Nobody has previously checked:

- Whether the chosen weights actually reflect the intended priorities.
- Whether some metrics are redundant (changing them makes no difference to the score).
- Whether the thresholds in `ai/config.yaml` are where the code actually reads them from.
- Whether realistic production device states (not just the specific test cases)
  produce sensible scores.

UQ provides a principled, quantitative way to answer all of these questions.

---

## Setup

### 1. Clone EasyVVUQ (if you don't already have it)

```bash
git clone https://github.com/UCL-CCS/EasyVVUQ.git /path/to/EasyVVUQ
```

### 2. Install EasyVVUQ in editable mode into the homepot venv

From the `homepot-client` root:

```bash
.venv/bin/pip install -e /path/to/EasyVVUQ
```

This follows the
[official install instructions](https://github.com/UCL-CCS/EasyVVUQ#installation)
and pulls in all required dependencies (chaospy, dill, SQLAlchemy, etc.) into the
existing homepot venv. No separate venv is needed.

> **Why editable (`-e`)?**  Changes to the EasyVVUQ source are immediately reflected
> without reinstalling — useful when developing or patching the library.

### 3. Run a study

Each study is self-contained. From the `homepot-client` root:

```bash
# Study 1
HOMEPOT_PATH=$(pwd) .venv/bin/python uq/study1_anomaly/run_anomaly_uq.py

# Study 2
HOMEPOT_PATH=$(pwd) .venv/bin/python uq/study2_simulator/run_simulator_uq.py

# Study 3
HOMEPOT_PATH=$(pwd) .venv/bin/python uq/study3_push/run_push_uq.py
```

Results are printed to stdout. Plots are saved to the `figs/` subdirectory of each
study (gitignored, created at runtime).

---

## Studies at a glance

| # | Study | Model under analysis | Method | Samples | Status |
|---|---|---|---|---|---|
| 1 | [Anomaly Detector Sensitivity](study1_anomaly/STUDY.md) | `ai/anomaly_detection.py` | PCE order 2, Sobol | 2 187 | ✅ Done |
| 2 | [Simulator Scenario Boundary Validation](study2_simulator/STUDY.md) | `DeviceSimulatorEndpoint._generate_metrics_for_scenario()` | MCSampler / Saltelli, Sobol | 16 200 | ✅ Done |
| 3 | [Push Notification Delivery Reliability](study3_push/STUDY.md) | Push notification delivery model | MCSampler / Saltelli, Sobol | 20 000 + 12 000 | ✅ Done |

---

## Directory structure

```
uq/
├── README.md                           ← this file — overview, setup, study index
├── study1_anomaly/                     ← Study 1: anomaly detector sensitivity (PCE)
│   ├── STUDY.md                        ← full background, methodology, results,
│   │                                      recommendations
│   ├── run_anomaly_uq.py               ← campaign script
│   ├── anomaly_runner.py               ← model wrapper
│   ├── anomaly_runner.template         ← EasyVVUQ GenericEncoder template
│   ├── figs/                           ← output plots (gitignored)
│   └── campaign_anomaly_uq/            ← EasyVVUQ working dir (gitignored)
├── study2_simulator/                   ← Study 2: simulator scenario validation (MCSampler)
│   ├── STUDY.md                        ← full background, methodology, results
│   ├── run_simulator_uq.py             ← campaign script
│   ├── anomaly_runner.py               ← model wrapper (local copy, independent of Study 1)
│   ├── anomaly_runner.template         ← EasyVVUQ GenericEncoder template
│   └── figs/                           ← output plots (gitignored)
└── study3_push/                        ← Study 3: push notification reliability (MCSampler)
    ├── STUDY.md                        ← full background, methodology, results
    ├── run_push_uq.py                  ← campaign script
    ├── push_runner.py                  ← deterministic expected-value runner
    ├── push_runner.template            ← EasyVVUQ GenericEncoder template
    └── figs/                           ← output plots (gitignored)
```

All `figs/` and `campaign_*/` directories are gitignored — they are regenerated on
each run. Plots are the primary runtime output of each study.
