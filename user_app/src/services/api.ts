import { apiBaseUrl } from '../config/api'

export interface DeviceRecord {
  site_id: string
  site_name: string
  device_id: string
  name: string
  device_type: string
  lifecycle_state: string
  connectivity_state: string
  health_state: string
  mac_address: string
  local_ip: string
  wan_ip: string
  os_details: string
  firmware_version: string
  last_seen: string | null
  last_heartbeat_at: string | null
  credential_status: string
  device_permissions: Record<string, boolean>
  capabilities: Record<string, boolean>
}

export interface PermissionsResponse {
  permissions: Record<string, boolean>
  capabilities: Record<string, boolean>
}

export interface DeviceStatus {
  lifecycle_state: string
  connectivity_state: string
  health_state: string
  last_heartbeat_at: string | null
}

export interface DeviceMetrics {
  cpu_percent: number | null
  memory_percent: number | null
  disk_percent: number | null
  network_latency_ms: number | null
  uptime_seconds: number | null
  timestamp: string | null
}

interface Headers {
  [key: string]: string
}

export interface UnpairOptions {
  reason?: string
  idempotencyKey?: string
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function deviceAuthHeaders(deviceId: string, apiKey: string): Headers {
  return { 'X-Device-ID': deviceId, 'X-API-Key': apiKey }
}

function asApiError(message: string, status: number): ApiError {
  return new ApiError(message, status)
}

export async function fetchDevice(deviceId: string, apiKey: string): Promise<DeviceRecord> {
  const res = await fetch(`${apiBaseUrl}/devices/device/${deviceId}`, {
    headers: deviceAuthHeaders(deviceId, apiKey),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw asApiError(body.detail || `Failed to fetch device (${res.status})`, res.status)
  }
  return res.json()
}

export async function fetchDeviceStatus(deviceId: string, apiKey: string): Promise<DeviceStatus> {
  const res = await fetch(`${apiBaseUrl}/agent/${deviceId}/status`, {
    headers: deviceAuthHeaders(deviceId, apiKey),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw asApiError(body.detail || `Failed to fetch status (${res.status})`, res.status)
  }
  const json = await res.json()
  return json.data as DeviceStatus
}

export async function fetchDeviceMetrics(
  deviceId: string,
  apiKey: string,
): Promise<DeviceMetrics> {
  const res = await fetch(`${apiBaseUrl}/agent/${deviceId}/metrics`, {
    headers: deviceAuthHeaders(deviceId, apiKey),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw asApiError(body.detail || `Failed to fetch metrics (${res.status})`, res.status)
  }
  const json = await res.json()
  return json.data as DeviceMetrics
}

export async function fetchPermissions(deviceId: string, apiKey: string): Promise<PermissionsResponse> {
  const res = await fetch(`${apiBaseUrl}/devices/device/${deviceId}/permissions`, {
    headers: deviceAuthHeaders(deviceId, apiKey),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw asApiError(body.detail || `Failed to fetch permissions (${res.status})`, res.status)
  }
  const json = await res.json()
  return json.data as PermissionsResponse
}

export async function updatePermissions(
  deviceId: string,
  apiKey: string,
  permissions: Record<string, boolean>,
): Promise<void> {
  const res = await fetch(`${apiBaseUrl}/devices/device/${deviceId}/permissions`, {
    method: 'PATCH',
    headers: { ...deviceAuthHeaders(deviceId, apiKey), 'Content-Type': 'application/json' },
    body: JSON.stringify({ permissions }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw asApiError(body.detail || `Failed to update permissions (${res.status})`, res.status)
  }
}

export async function bootstrapProvision(body: {
  site_id: string
  device_name: string
  device_type: string
  os_details: string
  bootstrap_key: string
}): Promise<{ device_id: string; api_key: string; site_id: string }> {
  const res = await fetch(`${apiBaseUrl}/devices/bootstrap-provision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw asApiError(err.detail || `Provision failed (${res.status})`, res.status)
  }
  const json = await res.json()
  return json.data
}

export async function claimDevice(body: {
  intent_id: string
  claim_token: string
  device_name: string
  device_type: string
  os_details: string
}): Promise<{ device_id: string; api_key: string; site_id: string }> {
  const res = await fetch(`${apiBaseUrl}/enrolment-intents/${body.intent_id}/claim`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw asApiError(err.detail || `Claim failed (${res.status})`, res.status)
  }
  const json = await res.json()
  return {
    device_id: json.device_id,
    api_key: json.api_key,
    site_id: json.site_id,
  }
}

export async function unpairDevice(
  deviceId: string,
  apiKey: string,
  options: UnpairOptions = {},
): Promise<void> {
  const res = await fetch(`${apiBaseUrl}/devices/device/${deviceId}/unpair`, {
    method: 'POST',
    headers: { ...deviceAuthHeaders(deviceId, apiKey), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reason: options.reason ?? 'User-initiated unpair from device settings',
      ...(options.idempotencyKey ? { idempotency_key: options.idempotencyKey } : {}),
    }),
  })
  if (!res.ok && res.status !== 404) {
    const body = await res.json().catch(() => ({}))
    throw asApiError(body.detail || `Unpair failed (${res.status})`, res.status)
  }
}
