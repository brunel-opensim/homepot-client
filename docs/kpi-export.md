# UK Demonstrator KPI Export

## 1. Purpose

This document is the stable reference for the implemented UK demonstrator KPI
calculation and export ([roadmap §5 and Phase 2](KPI-evaluation-roadmap.md)). It
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
- **Unit:** `%`. Null when there are no terminal commands.

### 2.3 MW-02 Command round-trip time

- **Formula:** `executed_at − created_at` in seconds, grouped by command type.
- **Population:** terminal commands with both `created_at` and `executed_at`.
  Commands without an `executed_at` are skipped.
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

```bash
homepot-client kpi-export \
  --start 2026-08-01T00:00:00Z \
  --end 2026-08-14T23:59:59Z \
  --provenance real \
  --out-dir evidence/uk-homepot/demo-run/exports
```

Options mirror the API (`--site-id`, `--device-id`, `--device-type`,
`--provenance`, `--format json|csv`, `--out-dir`). It writes
`kpi-export.json` (bundle) or `kpi-summary.csv` (summary) into `--out-dir`
and prints the calculation version and Git commit on completion.

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
- **MW-02 requires `executed_at`:** commands still in flight are excluded by the
  terminal-status rule.
- **A null `value` means an empty denominator**, not a failure — the
  numerator/denominator counts distinguish "0%" from "no data".
- **Percentiles on tiny samples:** with one value the p50/p95/max all equal
  that value; report sample counts alongside percentiles.