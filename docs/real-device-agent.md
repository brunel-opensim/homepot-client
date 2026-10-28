# Real Device Agent

The `homepot.agent` module is the backend-facing runtime for a real device
(GetFudo POS terminal). The agent registers with the backend, streams telemetry,
reports heartbeats, polls and executes approved commands, and retries failed
submissions.

## Registration and authentication

- `POST /api/v1/agent/register` performs a pre-authorized registration check.
  The `/register` endpoint validates `device_id` against an existing `Device`
  record, `api_key` against the stored `Device.api_key_hash`, and `site_id`
  against the site already associated with that device.
- Subsequent authenticated requests use credentials from the agent configuration.
- `homepot.agent.utils.device_dna` gathers host identity data used during
  registration and reporting.

## Runtime loops

`real_device_agent.py` (`run_agent`) runs several concurrent loops:

| Loop | Purpose |
| --- | --- |
| `telemetry_loop` | Sends device metrics to `POST /api/v1/agent/telemetry` on `telemetry_interval_seconds` (default 30 s) |
| `heartbeat_loop` | Reports agent liveness |
| `pending_commands_loop` | Polls for pending commands and acknowledges each one (`sent_at`) |
| `command_result_loop` | Reports terminal command results (`executed_at`) |
| `retry_flush_loop` | Flushes failed submissions with exponential backoff |
| `_watchdog_loop` | Local watchdog supervision |

### Telemetry payload

The telemetry loop sends:

```json
{
  "device_id": "android-pos-001",
  "site_id": "site-1234",
  "cpu_usage": 20.1,
  "memory_usage": 55.4,
  "disk_usage": 44.8,
  "uptime_seconds": 86400,
  "network_latency_ms": 8.4,
  "collection_interval_seconds": 30,
  "timestamp": "2026-04-13T12:00:30Z"
}
```

- `network_latency_ms` comes from `measure_network_latency_ms` and backs the
  PF-LAT KPI.
- `uptime_seconds` and `collection_interval_seconds` support PF-04 and EQ-02.
- A `pos` block is included only when `pos_signals_source` is configured; it is
  gated so unverified POS signals cannot be presented as pilot evidence.

## External WAN IP dependency

`device_dna.py` currently uses public IP discovery services to determine WAN IP
information, trying these providers in order:

- `https://api.ipify.org`
- `https://ifconfig.me/ip`
- `https://icanhazip.com`

This is a best-effort external dependency for metadata collection, not a hard
requirement for agent registration.

## Evidence recording

Telemetry and events produced by the agent are recorded with provenance
snapshotted at write time (`real`, `controlled`, or `simulated`). See
[Evidence Recording](provenance-and-outcomes.md) for the derivation rules and
the command/configuration outcome fields.
## Dashboard tabs and what they show

The Device Details page in the Dashboard has several tabs. Understanding
what each one tracks helps technicians diagnose issues.

### Push History
Shows **individual commands** sent to this device (via `DeviceCommand` records).
Each entry includes the command type, payload, status (pending → sent →
completed/failed), result (stdout/stderr/verification), and timestamps.

**Source**: Agent polls `GET /api/v1/devices/pending`, executes, and reports
via `PUT /api/v1/devices/{id}/commands/{cid}/status`.

### Job History
Shows **orchestrated operations** (via `Job` records). A Job is a site-level
or device-targeted operation created by the orchestrator when a technician
triggers an action on a site or device.

**What counts as a Job today:**
- POS payment config updates (site-wide or device-targeted)

**What does NOT create a Job:**
- Individual device commands (restart, update_config, install_program, etc.)
  — these are tracked in Push History, not Job History
- Background maintenance tasks — these were previously faked by the agent
  but have been removed; real devices no longer create synthetic job records

**Source**: Orchestrator creates jobs via `POST /api/v1/agent/jobs` when
processing site-level operations. The agent does NOT create jobs on its own.

### Live Logs
Shows real-time device log lines (via `ErrorLog` records). The agent posts
status snapshots every 30s (deduplicated) and structured events (command
execution, connectivity issues, resource warnings) as they occur.

**Source**: Agent posts to `POST /api/v1/agent/logs`.

### Audit Trail
Shows audit events (via `AuditLog` records): agent lifecycle (start/stop),
permission changes, and other significant events.

**Source**: Agent posts to `POST /api/v1/agent/audit`.

### Key distinction: Job vs. DeviceCommand

| | Job | DeviceCommand |
|--|-----|---------------|
| **Scope** | Site-wide (may target multiple devices) | Single device |
| **Created by** | Orchestrator (technician triggers site action) | Agent or technician (individual command) |
| **Tracks** | Overall operation status across devices | Single command execution |
| **Shown in** | Job History tab | Push History tab |

### Why Job History may show "No jobs"

For real devices, Job History only shows orchestrator-created jobs (site-wide
operations like POS config updates). If no such operations have targeted the
device, the tab correctly shows "No jobs". Individual commands are tracked in
Push History, not Job History.

Simulators and emulators may still generate synthetic job records for demo
visibility.
