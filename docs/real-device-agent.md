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