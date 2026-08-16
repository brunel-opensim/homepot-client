# Evidence Recording: Provenance and Outcome Tracking

## 1. Purpose

This document defines how evidence provenance and command/configuration
outcomes are recorded, so that exported KPI values (see
[KPI export](kpi-export.md)) are traceable to the telemetry and events that
produced them. It aligns the analytics telemetry documentation with the
implemented schema and the [evaluation roadmap](KPI-evaluation-roadmap.md) §3.1
provenance principles.

## 2. Provenance classes

Every exported row carries one of three lower-case provenance classes:

| Class | Meaning |
| --- | --- |
| `real` | Produced by a physical pilot device or an authoritative POS/application integration |
| `controlled` | Produced by a deterministic emulator or injected fault under a recorded test protocol |
| `simulated` | Random or seeded demonstration data |

`real`, `controlled`, and `simulated` results are never combined in one
headline value (roadmap §3.3).

## 3. Derivation and snapshot

The class is derived **at write time** from the device record by
`derive_provenance()` and snapshotted onto the row, so historical rows never
silently inherit a later change to the device's classification. The derivation
order is:

1. `device.config["device_source"]`:
   - `"emulator"` → `controlled`;
   - `"simulation"` → `simulated`;
   - `"physical"` → `real`;
2. otherwise, if `device.is_simulated` → `simulated`;
3. otherwise → `real`.

When the device record is not available, `derive_provenance` returns `None` and
no classification is stored, rather than a guessed one.

### 3.1 Snapshotted columns

| Table | Column | Notes |
| --- | --- | --- |
| `device_metrics` | `provenance` | Also snapshots `collection_interval_seconds` |
| `device_state_history` | `provenance` | |
| `configuration_history` | `provenance` | |
| `job_outcomes` | `provenance` | Present in schema; outside the EQ-01 tables |
| `error_logs` | `provenance` | Present in schema; outside the EQ-01 tables |
| `device_commands` | — | No snapshotted provenance; scoped at export time |

### 3.2 Collection metadata

`device_metrics.collection_interval_seconds` records the interval the reporting
agent was configured to use (the real agent sends this with every telemetry
sample; its default is 30 seconds). It is the source for the EQ-02
(completeness) gate, which is defined but not yet computed.

### 3.3 Export-time scoping

`device_commands` predates provenance snapshots, so command KPIs are scoped by
re-deriving each device's class at export time from the current device record.
This means a command's reported scope reflects the device's classification
today rather than at command time — see the limitation in
[KPI export](kpi-export.md) §10.

## 4. Command outcome tracking

`device_commands` records the full queue-to-execution lifecycle:

| Field | Meaning |
| --- | --- |
| `command_id` | Unique command identifier (UUID) |
| `command_type` | e.g. `restart`, `update_config`, `ping` |
| `payload` | Command arguments (JSON) |
| `status` | `pending`, `sent`, `completed`, `failed`, or `expired` |
| `result` | Execution result (JSON) |
| `created_at` | Queue time (server clock) |
| `sent_at` | Stamped when the command is handed to the agent (polling contract) |
| `executed_at` | Stamped when a terminal status is reported (server clock fallback) |

Terminal statuses are `completed`, `failed`, and `expired`; these form the
denominator of MW-01 and MW-02.

A command can only be queued for a device once its owner has granted the
command's required permission (`restart`/`shutdown` need `root_access`;
`update_config`/`update_pos_payment_config` need `filesystem_access`;
`health_check`/`restart_pos_app`/`run_command`/`run_script` need
`command_execution`; `ping` and `request_permission` need none). Command KPIs
therefore cover only the granted command types.

The agent polls for pending commands (`GET /api/v1/devices/{id}/pending` or
equivalent), acknowledges each one (stamping `sent_at`), executes it, and
reports the terminal result (stamping `executed_at`). Commands still in flight
remain `pending`/`sent` and are excluded from MW-01/MW-02 as non-terminal.

## 5. Configuration outcome tracking

`configuration_history` records configuration changes and their closed-loop
outcome, including rollback:

| Field | Meaning |
| --- | --- |
| `performance_before` | Metrics before the change (JSON) |
| `performance_after` | Metrics after the change (JSON) |
| `was_successful` | Whether the change achieved its result (`true`/`false`/null) |
| `was_rolled_back` | Whether the change was reverted |
| `rollback_reason` | Why it was rolled back |
| `rollback_success` | Whether the rollback restored the baseline (`true`/`false`/null) |
| `rollback_performance` | Metrics after the rollback (JSON) |
| `rolled_back_at` | Timestamp of the rollback |
| `provenance` | Snapshotted evidence class |

These fields back MW-03 (`was_successful`), MW-04 (improvement using
`performance_before`/`performance_after` and the healthy-status/response-time
rule), and MW-05 (restoring rollbacks using `rollback_success` or
`performance_before` vs `rollback_performance`).

## 6. Relationship to KPI calculations

The recorded rows are consumed by the [KPI export](kpi-export.md):

- `device_metrics` → EQ-01 (provenance coverage) and PF-LAT (latency
  percentiles);
- `device_state_history` → EQ-01;
- `configuration_history` → EQ-01, MW-03, MW-04, MW-05;
- `device_commands` → MW-01, MW-02.