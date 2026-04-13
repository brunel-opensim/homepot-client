# GetFudo Integration Roadmap (Part 2)

**Status**: In Progress  
**Target Audience**: Backend Developers, Agent Developers, GetFudo UI Team, QA  
**Goal**: Finalize local IPC and backend contracts so the GetFudo User App can integrate with real device agents without direct OS access.

---

## 1. Executive Summary

This roadmap defines the implementation and contract details for the Part 2 preparation phase:

1. Local IPC for desktop UI consumption.
2. Device DNA persistence and telemetry ingestion.
3. Automated device provisioning for setup wizard flow.
4. Frozen mock contracts for frontend stubs.

The outcome is a stable API and payload layer that unblocks GetFudo parallel development.

---

## 2. Architecture Strategy

### 2.1 Local IPC Strategy

The real device agent provides a lightweight local FastAPI server on `localhost`:

1. `GET /status`
2. `GET /health`
3. `GET /last-telemetry`

This design allows Electron/React clients to query runtime state without direct hardware or OS calls.

### 2.2 Backend Strategy

Backend captures and serves agent-state data through APIs:

1. `POST /api/v1/agent/register`
2. `POST /api/v1/agent/heartbeat`
3. `POST /api/v1/agent/telemetry`
4. `POST /api/v1/devices/provision`
5. `GET /api/v1/agent/{device_id}/status`

Device DNA fields persisted in `devices`:

- `os_details`
- `mac_address`
- `wan_ip`

Telemetry metrics persisted in `device_metrics`.

---

## 3. API Contract Summary

### 3.1 Telemetry API

**Endpoint**: `POST /api/v1/agent/telemetry`  
**Mode**: Single payload and bulk array payload supported.

Single payload:

```json
{
  "device_id": "physical-pos-001",
  "cpu_usage": 20.5,
  "memory_usage": 58.1,
  "disk_usage": 49.3,
  "timestamp": "2026-04-09T10:10:00+00:00"
}
```

Bulk payload:

```json
[
  {
    "device_id": "physical-pos-001",
    "cpu_usage": 20.5,
    "memory_usage": 58.1,
    "disk_usage": 49.3,
    "timestamp": "2026-04-09T10:10:00+00:00"
  },
  {
    "device_id": "physical-pos-001",
    "cpu_usage": 22.0,
    "memory_usage": 60.0,
    "disk_usage": 50.0,
    "timestamp": "2026-04-09T10:11:00+00:00"
  }
]
```

### 3.2 Provision API

**Endpoint**: `POST /api/v1/devices/provision`

Request:

```json
{
  "site_id": "site-001",
  "user_identity": "setup.user@getfudo.com",
  "device_name": "Front Counter POS",
  "device_type": "physical_terminal"
}
```

Response:

```json
{
  "status": "success",
  "message": "Device provisioned successfully",
  "data": {
    "device_id": "physical_terminal-a1b2c3d4",
    "device_token": "generated-token",
    "secret_key": "generated-secret",
    "site_id": "site-001",
    "created_at": "2026-04-09T10:15:00+00:00"
  }
}
```

### 3.3 Local IPC Status Example

`GET /status` response:

```json
{
  "device_id": "physical-pos-001",
  "status": "ONLINE",
  "last_heartbeat": "2026-04-09T10:05:00+00:00",
  "last_telemetry": {
    "device_id": "physical-pos-001",
    "cpu_usage": 21.2,
    "memory_usage": 54.3,
    "disk_usage": 47.8,
    "timestamp": "2026-04-09T10:05:00+00:00"
  }
}
```

---

## 4. Mock Contract Artifacts

Canonical stub files for GetFudo UI implementation:

1. `docs/contracts/mock_dna.json`
2. `docs/contracts/mock_telemetry.json`

These files are the frozen payload contract for development and QA mocking.

---

## 5. Delivery Checklist

1. Local IPC endpoints reachable from User App host.
2. Swagger/OpenAPI displays telemetry and provision endpoints.
3. DNA fields are persisted and queryable in `devices`.
4. Provision flow returns `device_id` and one-time `secret_key`.
5. Mock files are versioned and shared with GetFudo.
