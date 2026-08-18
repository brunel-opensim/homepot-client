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

### 2. Resource Usage (Low Impact)
High resource usage is often normal (e.g., during updates), so it carries less weight unless combined with stability issues.

| Metric | Threshold | Score Impact | Description |
| :--- | :--- | :--- | :--- |
| **CPU Usage** | > 90% | **+0.2** | Processor is under heavy load. |
| **Memory Usage** | > 90% | **+0.2** | RAM is near capacity. |
| **Disk Usage** | > 95% | **+0.2** | Storage is critically low. |

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
