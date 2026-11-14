# Anomaly Detection System

## Overview
The Anomaly Detection system in HomePot is designed to identify devices that are unstable, broken, or at risk of failure. Unlike traditional monitoring that alerts on every CPU spike, this system prioritizes **Stability** over **Resource Usage**.

The goal is to act as an "AI Technician" that filters out noise and highlights devices that actually need attention.

## Detection Strategy
The system calculates an **Anomaly Score** (0.0 to 1.0) for each monitored device based on a weighted set of heuristics.

*   **Score 0.0 - 0.5**: Normal operation.
*   **Score 0.5 - 0.8**: Warning (Degraded performance).
*   **Score > 0.8**: **CRITICAL** (Device is broken or breaking).

## Scoring Logic

The score is cumulative, capped at 1.0.

### 1. Stability Checks (High Impact)
These metrics indicate that a device is failing to perform its function.

| Metric | Threshold | Score Impact | Description |
| :--- | :--- | :--- | :--- |
| **Consecutive Failures** | >= 3 | **+0.8** | The device has failed its last 3 health checks (pings/HTTP checks). |
| **Flapping** | > 5 / hr | **+0.6** | The device state changed (e.g., Online -> Offline -> Online) more than 5 times in the last hour. |
| **Error Rate** | > 5% | **+0.5** | More than 5% of operations/requests are returning errors. |
| **Network Latency** | > 500ms | **+0.4** | Network response time is critically slow. |
| **Device Offline** | no recent heartbeat | **+0.4** | Active device has no recent heartbeat (offline). |
| **No Telemetry** | no metric row | **+0.3** | Device has no recent metric readings. |
| **Stale Telemetry** | last metric > 10 min | **+0.3** | Latest metric is older than 10 minutes. |

### 2. Resource Usage (Low Impact)
High resource usage is often normal (e.g., during updates), so it carries less weight unless combined with stability issues.

| Metric | Threshold | Score Impact | Description |
| :--- | :--- | :--- | :--- |
| **CPU Usage** | > 90% | **+0.2** | Processor is under heavy load. |
| **Memory Usage** | > 90% | **+0.2** | RAM is near capacity. |
| **Disk Usage** | > 90% | **+0.2** | Storage is critically low. |

## Reliability & Alert Persistence

### Is it "Real" AI?
Currently, the system uses a **Rule-Based Heuristic Engine**, not a black-box machine learning model. This ensures **High Reliability**.
*   It is **Deterministic**: If CPU > 90%, it alerts. Every time.
*   It is **Transparent**: You always know *why* an alert triggered (the math is clear).
*   It eliminates "Hallucinations": The system will not invent an alert based on a guess.

### Alert Visibility: Dashboard vs. Device Page
There is a distinction in how alerts are displayed across the application:

1.  **Dashboard (Real-Time + Persistent)**:
    *   Shows anomalies detected **right now** in memory (e.g., a sudden 5-second CPU spike) via the `ActiveAlertsTicker`.
    *   Shows persistent alerts stored in the database.
    *   *Purpose*: Immediate operational awareness.

2.  **Device Detail Page (Merged DB + AI Anomalies)**:
    *   Under the "Alerts" tab, this view merges formally logged database alerts with the live AI anomaly scan (`GET /api/v1/ai/anomalies`), tagging AI-sourced rows with an **AI Analysis** source badge and de-duplicating against the DB alerts by reason.
    *   The anomaly list is fetched on load and re-polled every few seconds so it stays live.
    *   *Purpose*: A single, current view of both committed and detected issues for that device.

## Triggering a scan

`GET /api/v1/ai/anomalies` is **pull-based**: it runs the rule-based scan on demand across active devices, and the Dashboard calls it on a polling cycle for near-real-time visibility. Note that calling it also syncs each device's `online`/`offline` status based on consecutive health-check failures.

**Response**:
```json
{
  "count": 1,
  "anomalies": [
    {
      "device_id": "DEVICE-8TKX-MVVG-U4EH",
      "device_name": "Web Dashboard 1-4",
      "score": 1.0,
      "reasons": ["High CPU: 92.5%", "High Memory: 88.0%"],
      "severity": "critical",
      "metrics": {
        "flapping_count": 12,
        "consecutive_failures": 5,
        "cpu_percent": 92.5,
        "memory_percent": 88.0
      },
      "timestamp": "2026-07-17T10:00:00Z"
    }
  ]
}
```

The response is limited to the top 5 anomalies by score.

## Configuration
Thresholds are defined in `ai/config.yaml` under the `anomaly_detection` section.

```yaml
anomaly_detection:
  sensitivity: 0.8
  window_size: 50
  thresholds:
    network_latency_ms: 200          # ms; above this flags "High Latency"
    cpu_percent: 90.0                # %; above this flags "High CPU"
    memory_percent: 90.0             # %; above this flags "High Memory"
    disk_percent: 90.0               # %; above this flags "High Disk Usage"
    error_rate: 0.05                 # ratio (5%); above this flags "High Error Rate"
    max_flapping_count: 5            # state changes per hour; above this flags "High Instability"
    consecutive_failures: 3          # health-check failures in a row; at/above this flags "System Failure"
```

`sensitivity` scales the final anomaly score (`score * sensitivity`, capped at `1.0`); it changes the reported score but not which thresholds fire. `window_size` is reserved and not currently applied.

## Multi-level detection

The system is moving from a single-tier detector to a **leveled** model so only
devices with **regular and persistent** problems are brought forward ("Monitored
Resources"), reducing noise.

### Foundation (implemented)

The first step is shipped and running in the API:

- **Persistence** — a new `anomaly_scans` table stores one row per device per
  scan (`score`, `level`, `severity`, `reasons`).
- **Background scan** — `ai_ops/anomaly_scan.py` runs a scheduled scan (default
  every 5 minutes) of all active devices, appends scan rows, and syncs
  online/offline status. It starts on API boot (`homepot.app.main`).
- **Level classification** — `classify_anomaly_level()` maps score plus
  persistence signals onto the 0-3 levels below. `GET /api/v1/ai/anomalies`
  now reads the latest persisted scans (level >= 2) instead of recomputing on
  every poll, with a cold-start fallback.
- **Flapping window fix** — flapping is now counted over the last `window_size`
  (default 50) health checks, not the last 5 (which could never exceed a
  threshold of 5, so "High Instability" could never fire).

Remaining: promotion/de-escalation of `is_monitored`, additional signals, and
the monitoring-tier UI (see plan below).

### Levels

| Level | Name | Trigger | Surfaces on Dashboard? | AI context? |
| :--- | :--- | :--- | :--- | :--- |
| 0 | Normal | No anomalies | No | No |
| 1 | Transient | Single threshold breach | No (logged only) | Only if queried |
| 2 | Persistent | Repeated breaches within a window (e.g. 3+ in 1 hour) OR consecutive failures >= 3 OR flapping | Yes — promoted to "Monitored" | Yes |
| 3 | Critical | Score >= 0.8, or a persistent alert with severity critical/high | Yes — alert banner | Yes + AI insight |

### Promotion and de-escalation
- **Promotion:** a device is auto-promoted to `is_monitored = True` when it reaches Level 2, so it enters the "Monitored Resources" set and is scanned on subsequent passes.
- **De-escalation:** after N consecutive clean scans (e.g. 5, ~25 minutes), a device that was auto-promoted is demoted back to normal and `is_monitored` is cleared (manual monitoring grants are preserved).
- Devices an operator has manually marked monitored are never auto-demoted.

### Persistence
Tier 1 (rule-based) results are stored in the `anomaly_scans` table (one row per
device per scan). This lets the system count breaches over a window instead of
reacting to a single sample, and gives de-escalation a clean-scan history to
count against.

### Background scan
A scheduled background scan runs in-process (default every 5 minutes) via
`ai_ops/anomaly_scan.run_anomaly_scan_loop`, started by `homepot.app.main`. It
computes persistence and keeps the Dashboard current without an AI query; the
pull-based endpoint reads the persisted results.

### Offline triage (deliberate vs unexpected)

Not every offline device is monitor-worthy. The scan distinguishes a deliberate
"goodbye" from an unexpected outage using the signal the agent already sends:

- **Graceful shutdown** — on app quit / OS shutdown the agent posts a final
  offline heartbeat (`status=OFFLINE, online=false`), which sets
  `device.status = offline` and clears the heartbeat. The scan treats this as
  *deliberately off*: it is scored Level 0 (not an anomaly) and its status is
  left exactly as the agent set it.
- **Unexpected outage** — a crash or power loss leaves `status = online` with a
  stale heartbeat; `compute_connectivity` reports `offline`. The scan treats
  this as a genuine anomaly (`connectivity_offline` contributes +0.4).

This is controlled by `anomaly_detection.ignore_graceful_offline` (default
`true`). A hard power-off (`kill -9`, pulling the plug) cannot send a goodbye —
no software can — so those are (correctly) classified `power_loss` /
`agent_crash` on the next start and remain monitor-worthy.

Still open (future signals): suppressing offline during closed/maintenance
hours via `SiteOperatingSchedule`, and offline-duration as a second axis.

### Additional candidate signals (HOMEPOT-specific)
Beyond the current metric thresholds, the following are worth considering:
- Repeated command failures (device cannot execute commands).
- Push-notification delivery failures.
- Disk filling trend (rising disk usage over time).
- Memory leak trend (rising memory over time).
- Device offline for > X minutes (beyond the connectivity threshold).
- No telemetry for > X minutes (partially implemented as "stale telemetry").

### Implementation plan (multi-PR)
1. **Persistence + background scan** (foundation): done — `anomaly_scans`
   table, scheduled scan loop, level classification, and an endpoint that reads
   stored results.
2. **Promotion / de-escalation**: auto-promote on Level 2, auto-demote after N
   clean scans, preserve manual grants.
3. **Additional signals**: command/push failures, trends.
4. **UI**: surface monitoring tier (normal/watchlisted/monitored/critical) on
   the device page and Dashboard.

### Decisions (recorded)
- **Scan storage**: a dedicated `anomaly_scans` table (append-only), not `Alert`
  rows, so clean scans are retained for de-escalation without polluting the
  alerts view.
- **Level 2 = persistent**: `score >= 0.8` → Level 3; consecutive failures or
  flapping or `persistent_breach_count` breaches in the window → Level 2; any
  other non-zero score → Level 1.
- **Flapping window**: last `window_size` (50) health checks.
- **Scan cadence**: 5 minutes, in-process (mirrors the retention loops), read
  from config `anomaly_detection.scan_interval_minutes`.
- **Monitoring model (operator + algorithm)**: keep `Device.is_monitored` as the
  operator's manual pin and add `Device.monitor_dismissed_until` for operator
  override. Effective "on Dashboard" = `is_monitored OR (auto-monitored AND not
  dismissed)`, where auto-monitored = latest scan level >= 2. An operator's
  "Remove from Dashboard" clears the pin and sets the dismiss cooldown; "Add to
  Dashboard" clears the dismiss.

### Open decisions
- Auto-promotion vs. operator approval for Level 2.
- De-escalation threshold (N clean scans).