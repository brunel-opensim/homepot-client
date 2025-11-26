# Device Metrics Collection API

> **Feature:** Device health monitoring with system, application, and network metrics  
> **Added:** November 19, 2025  
> **Status:** Active  
> **Version:** 1.0

## Overview

The Device Metrics Collection API allows devices to report detailed health and performance metrics to the HOMEPOT backend. This data enables:

- Real-time device monitoring
- Anomaly detection and alerting
- Predictive maintenance
- Performance trend analysis
- AI-powered insights (future)

## API Endpoints

### 1. Submit Device Health Check

**Endpoint:** `POST /api/v1/devices/{device_id}/health`

**Description:** Submit health check data with optional system, application, and network metrics.

**Authentication:** API Key required

#### Request Parameters

**Path Parameters:**
- `device_id` (string, required): Unique device identifier (e.g., "pos-terminal-001")

**Request Body:** JSON object with the following fields:

```json
{
  "is_healthy": true,
  "response_time_ms": 150,
  "status_code": 200,
  "endpoint": "/health",
  "response_data": {
    "status": "healthy",
    "version": "1.2.3"
  },
  "error_message": null,
  "system": {
    "cpu_percent": 65.5,
    "memory_percent": 80.0,
    "memory_used_mb": 1024,
    "memory_total_mb": 2048,
    "disk_percent": 60.0,
    "disk_used_gb": 120,
    "disk_total_gb": 200,
    "uptime_seconds": 86400
  },
  "app_metrics": {
    "app_version": "1.2.3",
    "transactions_count": 150,
    "errors_count": 2,
    "warnings_count": 5,
    "avg_response_time_ms": 350
  },
  "network": {
    "latency_ms": 45,
    "rx_bytes": 1024000,
    "tx_bytes": 512000
  }
}
```

#### Field Descriptions

**Required Fields:**
- `is_healthy` (boolean): Overall health status of the device
- `response_time_ms` (integer): Response time in milliseconds

**Optional Core Fields:**
- `status_code` (integer): HTTP status code (default: 200)
- `endpoint` (string): Health check endpoint path
- `response_data` (object): Additional device-specific data
- `error_message` (string): Error description if unhealthy

**Optional System Metrics:**
- `system.cpu_percent` (float): CPU usage percentage (0-100)
- `system.memory_percent` (float): Memory usage percentage (0-100)
- `system.memory_used_mb` (integer): Used memory in MB
- `system.memory_total_mb` (integer): Total memory in MB
- `system.disk_percent` (float): Disk usage percentage (0-100)
- `system.disk_used_gb` (integer): Used disk space in GB
- `system.disk_total_gb` (integer): Total disk space in GB
- `system.uptime_seconds` (integer): System uptime in seconds

**Optional Application Metrics:**
- `app_metrics.app_version` (string): Application version
- `app_metrics.transactions_count` (integer): Number of transactions processed
- `app_metrics.errors_count` (integer): Number of errors encountered
- `app_metrics.warnings_count` (integer): Number of warnings
- `app_metrics.avg_response_time_ms` (integer): Average response time in ms

**Optional Network Metrics:**
- `network.latency_ms` (integer): Network latency in milliseconds
- `network.rx_bytes` (integer): Bytes received
- `network.tx_bytes` (integer): Bytes transmitted

#### Response

**Success (200 OK):**
```json
{
  "message": "Health check recorded successfully",
  "device_id": "pos-terminal-001",
  "health_check_id": 123,
  "timestamp": "2025-11-19T10:00:00.000Z"
}
```

**Error (404 Not Found):**
```json
{
  "detail": "Device 'pos-terminal-001' not found"
}
```

**Error (422 Unprocessable Entity):**
```json
{
  "detail": [
    {
      "loc": ["body", "is_healthy"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

### 2. Device Metrics Simulator (Testing)

**Endpoint:** `POST /api/v1/simulator/device-metrics`

**Description:** Generate and submit simulated device metrics for testing purposes.

**Authentication:** Not required (development/testing only)

#### Query Parameters

- `device_id` (string, optional): Device ID to simulate (default: random)
- `is_healthy` (boolean, optional): Health status (default: true)

#### Response

**Success (200 OK):**
```json
{
  "message": "Simulated metrics submitted successfully",
  "device_id": "simulator-pos-abc123",
  "health_check_id": 124,
  "timestamp": "2025-11-19T10:01:00.000Z",
  "metrics": {
    "is_healthy": true,
    "response_time_ms": 145,
    "system": {
      "cpu_percent": 62.3,
      "memory_percent": 75.8,
      "memory_used_mb": 1520,
      "memory_total_mb": 2048,
      "disk_percent": 58.2,
      "disk_used_gb": 116,
      "disk_total_gb": 200,
      "uptime_seconds": 92340
    },
    "app_metrics": {
      "app_version": "1.2.3",
      "transactions_count": 142,
      "errors_count": 1,
      "warnings_count": 3,
      "avg_response_time_ms": 325
    },
    "network": {
      "latency_ms": 38,
      "rx_bytes": 985600,
      "tx_bytes": 456700
    }
  }
}
```

---

## Usage Examples

### Example 1: Minimal Health Check

```bash
curl -X POST \
  http://localhost:8000/api/v1/devices/pos-terminal-001/health \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "is_healthy": true,
    "response_time_ms": 100
  }'
```

### Example 2: Full Metrics Report

```bash
curl -X POST \
  http://localhost:8000/api/v1/devices/pos-terminal-001/health \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "is_healthy": true,
    "response_time_ms": 150,
    "status_code": 200,
    "system": {
      "cpu_percent": 65.5,
      "memory_percent": 80.0,
      "disk_percent": 60.0,
      "uptime_seconds": 86400
    },
    "app_metrics": {
      "app_version": "1.2.3",
      "transactions_count": 150,
      "errors_count": 2
    },
    "network": {
      "latency_ms": 45
    }
  }'
```

### Example 3: Unhealthy Device Report

```bash
curl -X POST \
  http://localhost:8000/api/v1/devices/pos-terminal-001/health \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "is_healthy": false,
    "response_time_ms": 5000,
    "status_code": 500,
    "error_message": "Database connection timeout",
    "system": {
      "cpu_percent": 95.0,
      "memory_percent": 98.0
    }
  }'
```

### Example 4: Generate Test Metrics

```bash
# Default healthy device
curl -X POST http://localhost:8000/api/v1/simulator/device-metrics

# Custom device ID
curl -X POST "http://localhost:8000/api/v1/simulator/device-metrics?device_id=test-pos-123"

# Simulate unhealthy device
curl -X POST "http://localhost:8000/api/v1/simulator/device-metrics?is_healthy=false"
```

---

## Device Implementation Guide

### Python Example

```python
import requests
import psutil
import time

class HomepotHealthReporter:
    def __init__(self, device_id, api_url, api_key):
        self.device_id = device_id
        self.api_url = api_url
        self.api_key = api_key
        self.start_time = time.time()
        
    def collect_system_metrics(self):
        """Collect system resource metrics using psutil."""
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": cpu,
            "memory_percent": memory.percent,
            "memory_used_mb": memory.used // (1024 * 1024),
            "memory_total_mb": memory.total // (1024 * 1024),
            "disk_percent": disk.percent,
            "disk_used_gb": disk.used // (1024 * 1024 * 1024),
            "disk_total_gb": disk.total // (1024 * 1024 * 1024),
            "uptime_seconds": int(time.time() - self.start_time)
        }
    
    def collect_app_metrics(self, transactions, errors, warnings, avg_time):
        """Collect application-specific metrics."""
        return {
            "app_version": "1.2.3",
            "transactions_count": transactions,
            "errors_count": errors,
            "warnings_count": warnings,
            "avg_response_time_ms": avg_time
        }
    
    def send_health_check(self, is_healthy=True, transactions=0, errors=0):
        """Send health check with metrics to HOMEPOT backend."""
        start = time.time()
        
        payload = {
            "is_healthy": is_healthy,
            "response_time_ms": int((time.time() - start) * 1000),
            "system": self.collect_system_metrics(),
            "app_metrics": self.collect_app_metrics(
                transactions=transactions,
                errors=errors,
                warnings=0,
                avg_time=350
            )
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/devices/{self.device_id}/health",
                json=payload,
                headers={"X-API-Key": self.api_key},
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to send health check: {e}")
            return None

# Usage
reporter = HomepotHealthReporter(
    device_id="pos-terminal-001",
    api_url="http://homepot.local:8000/api/v1",
    api_key="your-api-key"
)

# Send health check every minute
while True:
    result = reporter.send_health_check(
        is_healthy=True,
        transactions=150,
        errors=2
    )
    print(f"Health check sent: {result}")
    time.sleep(60)
```

---

## Data Storage

All metrics are stored in the `health_checks` table with the following structure:

```sql
CREATE TABLE health_checks (
    id SERIAL PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    is_healthy BOOLEAN NOT NULL,
    response_time_ms INTEGER,
    status_code INTEGER,
    endpoint VARCHAR(200),
    response_data JSONB,  -- Contains system, app_metrics, network
    error_message TEXT,
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

The `response_data` JSONB field stores all optional metrics, allowing flexible schema evolution.

---

## Querying Metrics

### Get Recent Health Checks

```sql
SELECT 
    d.device_id,
    hc.is_healthy,
    hc.response_time_ms,
    hc.response_data->'system'->>'cpu_percent' AS cpu_percent,
    hc.response_data->'system'->>'memory_percent' AS memory_percent,
    hc.checked_at
FROM health_checks hc
JOIN devices d ON hc.device_id = d.id
WHERE hc.checked_at > NOW() - INTERVAL '1 hour'
ORDER BY hc.checked_at DESC;
```

### Find High CPU Usage

```sql
SELECT 
    d.device_id,
    (hc.response_data->'system'->>'cpu_percent')::float AS cpu_percent,
    hc.checked_at
FROM health_checks hc
JOIN devices d ON hc.device_id = d.id
WHERE (hc.response_data->'system'->>'cpu_percent')::float > 80.0
ORDER BY hc.checked_at DESC
LIMIT 10;
```

---

## Best Practices

### For Device Developers

1. **Report regularly:** Send health checks every 30-60 seconds
2. **Include context:** Always send system metrics if available
3. **Report errors:** Set `is_healthy=false` and include `error_message`
4. **Handle failures gracefully:** Queue metrics locally if backend is unavailable
5. **Use appropriate precision:** Round percentages to 1-2 decimal places

### For Backend Integration

1. **Index frequently queried fields:** Create indexes on `checked_at`, `device_id`
2. **Implement retention policy:** Archive old health checks (>30 days)
3. **Monitor data volume:** Set up alerts for unusual metric submission rates
4. **Validate ranges:** Ensure CPU/memory/disk percentages are 0-100
5. **Alert on anomalies:** Set up automated alerts for unhealthy devices

---

## Future Enhancements

The following features are planned for future releases:

- Real-time WebSocket streaming of metrics
- Aggregated metrics API (hourly/daily summaries)
- Anomaly detection and automated alerting
- Predictive maintenance using ML models
- Custom metric types (device-specific)
- Metric visualization dashboard

---

## Troubleshooting

### Device not receiving acknowledgment

**Problem:** POST request times out or returns 404

**Solutions:**
1. Verify device is registered in HOMEPOT
2. Check API key is valid
3. Ensure `device_id` matches exactly (case-sensitive)
4. Check backend logs for errors

### High resource usage reported incorrectly

**Problem:** System metrics show >100% or negative values

**Solutions:**
1. Update device monitoring library (psutil, etc.)
2. Verify metric calculation logic
3. Check for integer overflow in calculations

### Metrics not visible in backend

**Problem:** Health checks submitted but not queryable

**Solutions:**
1. Verify database connection
2. Check PostgreSQL logs for constraint violations
3. Ensure JSONB structure matches schema
4. Review backend application logs

---

## Related Documentation

- [API Testing Guide](api-testing-guide.md)
- [Database Guide](database-guide.md)
- [Device Management](pos-management.md)
- [Push Notifications](push-notification.md)

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/brunel-opensim/homepot-client/issues
- Documentation: https://brunel-opensim.github.io/homepot-client/
