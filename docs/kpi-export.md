# UK Demonstrator KPI Export

## 1. Purpose

This document is the stable reference for the implemented UK demonstrator KPI
calculation and export ([roadmap §5 and Phase 2](kpi-evaluation-roadmap.md)). It
defines each exported KPI, its formula, its unit, its population, and the exact
behaviour of the export API and command-line tool. It is the source of truth for
"definitions, units, and limitations" of the machine-readable evidence output.

Every export is versioned and reproducible: it records the calculation version,
the Git commit of the calculation code, the reporting timezone, the filters, and
the generation timestamp, and it ships the raw evidence rows that back each
value.

!!! note "Scope"
    Only the KPIs listed below are currently computed by the export. The rest of
    the roadmap register (for example EQ-02 to EQ-05, PF-01 to PF-07, MW-06/07,
    and AI-01 to AI-04) remains defined but **not yet computed** and is out of
    scope for this export until its calculation and evidence source exist.

## 2. Implemented KPI register

| ID | KPI | Unit | Value definition |
| --- | --- | --- | --- |
| EQ-01 | Provenance coverage | `%` | rows with valid provenance / eligible rows × 100, per table |
| MW-01 | Command completion rate | `%` | completed commands / terminal commands × 100 |
| MW-02 | Command round-trip time | `seconds` | `executed_at − created_at`, by command type, p50/p95/max |
| MW-03 | Configuration-change success | `%` | successful changes / attempted changes × 100 |
| MW-04 | Verified improvement rate | `%` | improved changes / verified successful changes × 100 |
| MW-05 | Rollback effectiveness | `%` | restoring rollbacks / attempted rollbacks × 100 |
| PF-LAT | Device-reported network latency | `ms` | `network_latency_ms` percentiles from `device_metrics`, p50/p95/max |

The unit map is recorded verbatim in every export manifest:

```json
{
  "EQ-01": "%",
  "MW-01": "%",
  "MW-02": "seconds",
  "MW-03": "%",
  "MW-04": "%",
  "MW-05": "%",
  "PF-LAT": "ms"
}
```

### 2.1 EQ-01 Provenance coverage

- **Formula:** rows with a valid `provenance` value / eligible rows in the
  window × 100.
- **Population:** rows in `device_metrics`, `device_state_history`, and
  `configuration_history` (entity type `device`) within the window.
- **Grouping:** one result per table (`device_metrics`, `device_state_history`,
  `configuration_history`).
- **Unit:** `%`. Null when the denominator is 0.
- **Gate:** no operational KPI may be labelled **Validated** when its underlying
  evidence fails EQ-01 (roadmap §5.1).

### 2.2 MW-01 Command completion rate

- **Formula:** completed commands / terminal commands × 100.
- **Population:** `device_commands` created within the window. Terminal statuses
  are `COMPLETED`, `FAILED`, and `EXPIRED`. Non-terminal commands (for example
  `PENDING`/`SENT`) are counted in `exclusions` and never form the denominator.
  Commands can only be queued for a device once its owner has granted the
  command's required permissions (see §10), so this population is limited to
  granted command types.
- **Unit:** `%`. Null when there are no terminal commands.

### 2.3 MW-02 Command round-trip time

- **Formula:** `executed_at − created_at` in seconds, grouped by command type.
- **Population:** terminal commands with both `created_at` and `executed_at`.
  Commands without an `executed_at` are skipped. As with MW-01, only commands
  the device owner has granted the required permissions for are eligible.
- **Statistics:** p50, p95, and maximum, using the linear-interpolation
  percentile definition in §5.
- **Unit:** `seconds`, rounded to 3 decimal places. Null for an empty group.
- **Grouping:** `{"command_type": "<type>", "statistic": "p50"|"p95"|"max"}`.

### 2.4 MW-03 Configuration-change success

- **Formula:** successful changes / attempted changes × 100.
- **Population:** `configuration_history` rows (entity type `device`) in the
  window. Attempted changes are rows where `was_successful` is not null; rows
  with `was_successful IS NULL` are counted in `exclusions`.
- **Unit:** `%`. Null when there are no attempted changes.

### 2.5 MW-04 Verified improvement rate

- **Formula:** improved changes / verified successful changes × 100.
- **Population:** successful changes (`was_successful = true`) that also have
  both `performance_before` and `performance_after`. Successful changes lacking
  a before/after window are counted in `exclusions`.
- **"Improved" definition (`_is_improved`):** the after-state reports a healthy
  status (`healthy`, `ok`, or `online`); otherwise, when no status is present,
  the after-state response time did not regress (`response_time_ms` after ≤
  before).
- **Unit:** `%`. Null when there are no verified changes.

### 2.6 MW-05 Rollback effectiveness

- **Formula:** restoring rollbacks / attempted rollbacks × 100.
- **Population:** `configuration_history` rows in the window with
  `was_rolled_back = true`.
- **"Restoring" definition:** `rollback_success = true`, or, when
  `rollback_success` is null, `_is_improved(performance_before,
  rollback_performance)`.
- **Unit:** `%`. Null when there are no attempted rollbacks.

### 2.7 PF-LAT Device-reported network latency

- **Formula:** percentiles of `device_metrics.network_latency_ms`.
- **Population:** `device_metrics` rows in the window with a non-null
  `network_latency_ms`; rows with null latency are ignored.
- **Statistics:** p50, p95, and maximum.
- **Unit:** `ms`, rounded to 2 decimal places. Null for an empty population.
- **Grouping:** `{"statistic": "p50"|"p95"|"max"}`.

## 3. Provenance scoping

Filters restrict the population to one provenance class. When no provenance
filter is given, results are computed for **every** scope: `all`, `real`,
`controlled`, and `simulated` (the roadmap §3.1 classes, lower-cased).

Tables that snapshot a `provenance` column at write time
(`device_metrics`, `device_state_history`, `configuration_history`) are filtered
directly on that column. `device_commands` predates provenance snapshots, so
command KPIs are scoped by deriving each device's classification **at export
time** from the device record. The derivation is:

1. `device.config["device_source"]` — `emulator` → `controlled`,
   `simulation` → `simulated`, `physical` → `real`;
2. otherwise `device.is_simulated` → `simulated`;
3. otherwise `real`.

See [Evidence recording](provenance-and-outcomes.md) for the write-time
snapshot behaviour.

## 4. Export formats

### 4.1 JSON bundle

`GET /api/v1/kpi/export` with `format=json` (default) returns a versioned
bundle with three sections:

- **`manifest`** — calculation metadata (see §6);
- **`kpis`** — the machine-readable KPI summary (one object per KPI and group);
- **`raw`** — the in-window raw evidence rows that back the calculations
  (`device_metrics`, `device_state_history`, `configuration_history`, and
  `device_commands`).

Each KPI object carries:

| Field | Meaning |
| --- | --- |
| `kpi_id` | Register ID, e.g. `MW-02` |
| `name` | Human-readable KPI name |
| `formula` | Plain-text calculation description |
| `unit` | Reported unit (`%`, `seconds`, `ms`) |
| `value` | Computed value, or `null` when the denominator is 0 |
| `numerator` | Numerator count |
| `denominator` | Denominator count |
| `exclusions` | Rows excluded by the KPI's own definition |
| `sample_count` | Rows used for the value |
| `provenance` | Scope: `all`, `real`, `controlled`, or `simulated` |
| `group` | Grouping keys, e.g. `{"command_type": "ping", "statistic": "p50"}` |

### 4.2 CSV summary

`format=csv` returns the KPI summary table as `kpi-summary.csv`, with the
manifest embedded as `# manifest: {...}` comment rows so the file is
self-describing for a reviewer. Columns: `kpi_id`, `name`, `formula`, `unit`,
`value`, `numerator`, `denominator`, `exclusions`, `sample_count`,
`provenance`, `group`.

The CSV is a summary only — the raw evidence rows are available in the JSON
bundle or directly from the database.

## 5. Percentile definition

Percentiles use linear interpolation between the two nearest ranks of the
sorted sample (`p = (n − 1) · q`, lower and upper ranks, fractional
interpolation), so p50/p95 are well defined for small samples. A single-value
sample returns that value; an empty sample returns `null`.

## 6. Manifest contract

Every export includes the following metadata:

| Field | Meaning |
| --- | --- |
| `run_id` | Unique run identifier (UTC timestamp, e.g. `20260816T220500Z`; overridable via `--run-id`) |
| `generated_at` | Generation timestamp, UTC ISO-8601 |
| `timezone` | Reporting timezone (`UTC`) |
| `calculation_version` | Calculation code version (`1.0.0`) |
| `git_commit` | Short Git commit of the calculation code (`unknown` when unavailable) |
| `units` | The KPI unit map from §2 |
| `provenance_scopes` | Scopes the export was computed for |
| `filters` | `start`, `end`, `site_id`, `device_id`, `device_type`, `provenance` |

A reviewer can pin every exported value to a specific revision of the
calculation code via `calculation_version` + `git_commit`.

## 7. Using the export

### 7.1 REST API

`GET /api/v1/kpi/export` (authenticated).

| Query parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `start` | ISO-8601 datetime | required | Window start (inclusive), UTC |
| `end` | ISO-8601 datetime | required | Window end (inclusive), UTC |
| `site_id` | string | — | Restrict to devices at this site |
| `device_id` | string | — | Restrict to this device |
| `device_type` | string | — | Restrict to this device type |
| `provenance` | string | — | `real`, `controlled`, or `simulated` |
| `format` | string | `json` | `json` (bundle) or `csv` (summary) |

Validation: an invalid `format` or `provenance` returns `422`; `start` after
`end` returns `400`.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/kpi/export?start=2026-08-01T00:00:00Z&end=2026-08-14T23:59:59Z&provenance=real&format=json"
```

### 7.2 Command-line tool

Run from the repository root:

```bash
./scripts/kpi-export.sh \
  --start 2026-08-01T00:00:00Z \
  --end 2026-08-14T23:59:59Z \
  --provenance real
```

`scripts/kpi-export.sh` resolves the venv and database URL so the command works
from the repo root; when the venv is active, `homepot-client kpi-export ...` is
equivalent. Options mirror the API (`--site-id`, `--device-id`, `--device-type`,
`--provenance`, `--run-id`, `--format json|csv`, `--out-dir`). It writes
`kpi-export.json` (bundle) or `kpi-summary.csv` (summary) and prints the run ID,
calculation version, and Git commit on completion.

The default `--out-dir` is `kpi-evidence/<run-id>`, where `<run-id>` is a UTC
timestamp generated per run (override with `--run-id`, e.g.
`UK-E01-rehearsal-1`). `kpi-evidence/` is a repository-root directory that is
gitignored except for its `README.md`, mirroring `logs/`. Pass an explicit
`--out-dir` to write elsewhere. See `kpi-evidence/README.md`.

## 8. Reproducibility requirements

For a value to be reproducible from a clean database snapshot:

- timestamps are stored and compared in UTC and the reporting timezone is
  recorded (`UTC`);
- the evaluation window is frozen before calculating results;
- site, device, type, and provenance filters are recorded in the manifest;
- numerator, denominator, exclusions, and sample count are retained for every
  rate;
- the calculation code is versioned and the Git commit is recorded;
- `REAL`, `CONTROLLED`, and `SIMULATED` results are never combined in one
  headline value — they are reported per scope.

## 9. Data-quality gates

The roadmap defines evidence-quality gates EQ-01 to EQ-05 (§5.1). Of these, only
**EQ-01 (provenance coverage)** is computed today and appears in every export.
The remaining gates (telemetry completeness, freshness, continuity, and valid
record rate) are defined but not yet calculated; their thresholds remain **TBD**
until frozen in Phase 0.

!!! warning "Gate language"
    "Implemented" (code path + automated tests) does **not** imply
    **Validated** (pre-agreed threshold met on `REAL` evidence). Apply the
    claim-maturity labels from roadmap §3.2 when reporting results.

## 10. Limitations

- **No real pilot evidence yet:** until Phase 4, exported values are rehearsal
  evidence at best (`CONTROLLED` or `SIMULATED`); do not present them as a
  pilot result.
- **Thresholds are not frozen:** acceptance thresholds in the register remain
  **TBD** until the Phase 0 freeze with the UK use-case owner.
- **EQ-02 to EQ-05 are not computed:** freshness, continuity, completeness, and
  valid-record-rate gates have no implementation yet.
- **`device_commands` provenance is derived at export time**, not snapshotted,
  so command KPI scopes reflect the device's classification *today* rather than
  at command time.
- **MW-01/MW-02 are permission-gated:** a command can only be queued once the
  device owner has granted its required permissions (e.g. `restart`/`shutdown`
  need `root_access`, `update_config` needs `filesystem_access`; `ping` and
  `request_permission` need none). Command KPIs therefore describe only the
  granted command types, not every possible management action, and a device
  that grants no permissions contributes no command evidence.
- **MW-02 requires `executed_at`:** commands still in flight are excluded by the
  terminal-status rule.
- **A null `value` means an empty denominator**, not a failure — the
  numerator/denominator counts distinguish "0%" from "no data".
- **Percentiles on tiny samples:** with one value the p50/p95/max all equal
  that value; report sample counts alongside percentiles.

## 11. Interpreting the results

The KPIs form a layered assessment — read them in order, because a failing
lower layer disqualifies the ones above it:

| Layer | Question | KPIs |
| --- | --- | --- |
| Trust | Can I trust the data? | EQ-01 |
| Health | Is the fleet healthy? | PF-LAT |
| Control | Can I control devices? | MW-01, MW-02 |
| Change | Can I change them safely? | MW-03, MW-04, MW-05 |

### 11.1 Reading each KPI

- **EQ-01 (provenance coverage)** — the trust gate. Confirm 100% before relying
  on any other value; below 100% means some rows are untagged, so real,
  controlled, and simulated evidence cannot be separated.
- **PF-LAT (network latency)** — read the p50/p95/max *spread*, not a single
  value. p50 is the typical experience, p95 the tail, max the worst case; a
  wide p50→p95 gap indicates intermittent degradation rather than a steadily
  slow link.
- **MW-01 (command completion)** — below 100% means commands are failing or
  expiring (devices offline, agents unresponsive, or required permissions not
  granted — see §10). Use `exclusions` to separate still-in-flight commands
  from genuine failures.
- **MW-02 (command round-trip time)** — watch the p95 more than the mean: it
  surfaces slow commands even while completion is still 100%. A rising trend
  means the queue→agent→execution pipeline is degrading.
- **MW-03/04/05 (change management)** — read as a closed loop: MW-03 (did it
  apply) → MW-04 (did it actually improve health) → MW-05 (did rollback
  recover). A change can apply (MW-03 = 100%) yet not improve (MW-04 low);
  MW-05 is the safety-net metric that gives change control its confidence.

### 11.2 The provenance lens

Read and report each scope separately — the same number means different things:

- `real` — production performance (the only scope to report as a result).
- `controlled` — rehearsal and fault-injection runs, validating detection and
  recovery before the real thing.
- `simulated` — demonstration data only; never present as a result.

See §3 for how each class is derived.

### 11.3 Caveats when reading values

- `value: null` is an empty denominator (no data), not a failure — check
  `numerator`/`denominator` to distinguish "0%" from "no data" (§10).
- With tiny samples a single event swings a rate to 0% or 100%; always read
  `sample_count` beside the value, and treat percentiles on one or two points
  with caution (§5).
- Thresholds are TBD, so judge by **trend across runs** (compare `run_id`s)
  rather than a single absolute value; the manifest's `git_commit` +
  `calculation_version` make runs comparable (§6).
- Cross-check the AI assistant's trust envelope: a low Gate B score (stale or
  incomplete telemetry) should be reflected in the same run's KPIs.

### 11.4 Suggested workflow

1. Run the export over the operational window of interest, scoped by
   site/device/type/provenance (§7).
2. Read the manifest to pin the window and population (§6).
3. Check EQ-01 = 100%, then PF-LAT, then MW-01/02, then MW-03/04/05.
4. Report each scope separately, with `sample_count` beside every percentage.