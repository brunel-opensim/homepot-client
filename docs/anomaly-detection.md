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

## Configuration
Thresholds are defined in `ai/config.yaml` under the `anomaly_detection` section.

```yaml
anomaly_detection:
  sensitivity: 0.8
  thresholds:
    max_latency_ms: 500
    max_error_rate: 0.05
    max_flapping_count: 5
    consecutive_failures: 3
```

## API Usage & Frequency
The anomaly detection is **Pull-Based** (On-Demand), meaning the calculation runs whenever the API is called.

*   **Trigger**: The Dashboard automatically calls this API every **30 seconds**.
*   **Effect**: This provides "Near Real-Time" monitoring for any user viewing the dashboard.
*   **Endpoint**: `GET /api/v1/ai/anomalies`

**Response**:
```json
{
  "count": 1,
  "anomalies": [
    {
      "device_id": "dev-123",
      "device_name": "POS Terminal 1",
      "score": 1.0,
      "severity": "critical",
      "metrics": {
        "flapping_count": 12,
        "consecutive_failures": 5,
        "cpu_percent": 45.0
      },
      "timestamp": "2025-12-30T10:00:00Z"
    }
  ]
}
```
