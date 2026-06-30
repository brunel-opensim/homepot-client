# HOMEPOT UserApp — API Endpoints


## 1. Device Provisioning

- **Method:** POST
- **Endpoint:** `/api/v1/devices/provision`
- **Page / Module:** Page 1 — Setup Wizard
- **Status:** Already built — `enrollment_method` is planned and not yet in backend schema
- **Backend file:** `backend/src/homepot/app/api/API_v1/Endpoints/DeviceProvisionEndpoint.py`

**Request:**
```json
{
  "sso_token": "eyJhbGciOi...",
  "site_id": "site-001",
  "user_identity": "kasi@company.com",
  "device_name": "Kasi-Laptop",
  "device_type": "physical_terminal",
  "enrollment_method": "self-enrolled"    // planned — not yet in backend schema
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "device_id": "physical-terminal-a1b2c3d4",
    "api_key": "mM2....",
    "site_id": "site-001",
    "created_at": "2026-06-16T10:00:00Z"
  }
}
```

---

## 2. Device Heartbeat

- **Method:** POST
- **Endpoint:** `/api/v1/agent/heartbeat`
- **Page / Module:** Page 2 — Home Dashboard
- **Status:** Already built
- **Backend file:** `backend/src/homepot/app/api/API_v1/Endpoints/AgentHeartbeatEndpoint.py`

**Request:**
```json
{
  "device_id": "physical-terminal-a1b2c3d4",
  "timestamp": "2026-06-16T10:45:00Z"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Heartbeat updated successfully",
  "data": {
    "device_id": "physical-terminal-a1b2c3d4"
  }
}
```

---

## 3. Submit Telemetry

- **Method:** POST
- **Endpoint:** `/api/v1/agent/telemetry`
- **Page / Module:** Page 2 — Home Dashboard
- **Status:** Already built
- **Backend file:** `backend/src/homepot/app/api/API_v1/Endpoints/AgentTelemetryEndpoint.py`

**Request:**
```json
{
  "device_id": "physical-terminal-a1b2c3d4",
  "cpu_usage": 42.0,
  "memory_usage": 61.0,
  "disk_usage": 28.0,
  "timestamp": "2026-06-16T10:50:00Z"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Telemetry saved successfully",
  "data": {
    "saved_count": 1
  }
}
```

---

## 4. Get Device Status

- **Method:** GET
- **Endpoint:** `/api/v1/agent/{device_id}/status`
- **Page / Module:** Page 2 — Home Dashboard
- **Status:** Already built
- **Backend file:** `backend/src/homepot/app/api/API_v1/Endpoints/AgentStatusEndpoint.py`

**Request:** No body — `device_id` passed in URL.

**Response:**
```json
{
  "status": "success",
  "data": {
    "device_id": "physical-terminal-a1b2c3d4",
    "status": "ONLINE"
  }
}
```

---

## 5. Get Permissions

- **Method:** GET
- **Endpoint:** `/api/v1/agent/{device_id}/permissions`
- **Page / Module:** Page 3 — Permissions
- **Status:** Need to build

**Request:** No body — `device_id` passed in URL.

**Response:**
```json
{
  "status": "success",
  "data": {
    "device_id": "physical-terminal-a1b2c3d4",
    "permissions": {
      "root_access": true,
      "process_monitoring": true,
      "filesystem_access": false,
      "network_monitoring": true
    }
  }
}
```

---

## 6. Update Permissions

- **Method:** PATCH
- **Endpoint:** `/api/v1/agent/{device_id}/permissions`
- **Page / Module:** Page 3 — Permissions
- **Status:** Need to build

**Request:**
```json
{
  "permissions": {
    "root_access": true,
    "process_monitoring": true,
    "filesystem_access": true,
    "network_monitoring": true
  }
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Permissions updated successfully",
  "data": {
    "device_id": "physical-terminal-a1b2c3d4",
    "updated_at": "2026-06-16T11:00:00Z"
  }
}
```

---

## 7. Device DNA Update

- **Method:** POST
- **Endpoint:** `/api/v1/agent/device-dna`
- **Page / Module:** Page 4 — Device Info
- **Status:** Already built
- **Backend file:** `backend/src/homepot/app/api/API_v1/Endpoints/AgentRegisterEndpoint.py`

**Request:**
```json
{
  "device_id": "physical-terminal-a1b2c3d4",
  "mac_address": "A1:B2:C3:D4:E5:F6",
  "os_details": "Linux 6.17",
  "local_ip": "192.168.1.101",
  "wan_ip": "203.0.113.10",
  "site_id": "site-001",
  "device_name": "Kasi-Laptop"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "device_id": "physical-terminal-a1b2c3d4",
    "mac_address": "A1:B2:C3:D4:E5:F6",
    "os_details": "Linux 6.17",
    "local_ip": "192.168.1.101"
  }
}
```

---

## 8. Unpair Device

- **Method:** POST
- **Endpoint:** `/api/v1/agent/{device_id}/unpair`
- **Page / Module:** Page 4 — Device Info
- **Status:** Need to build

**Request:**
```json
{
  "device_id": "physical-terminal-a1b2c3d4"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Device unpaired successfully"
}
```

---

## 9. Check for Updates

- **Method:** GET
- **Endpoint:** `/api/v1/agent/version/latest`
- **Page / Module:** Page 4 — Device Info
- **Status:** Need to build

**Request:** No body.

**Response:**
```json
{
  "status": "success",
  "data": {
    "current_version": "v0.1.0",
    "latest_version": "v0.1.1",
    "update_available": true,
    "download_url": "https://..."
  }
}
```
