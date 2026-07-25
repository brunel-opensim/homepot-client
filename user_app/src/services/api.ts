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

interface Headers {
  [key: string]: string
}

function deviceAuthHeaders(deviceId: string, apiKey: string): Headers {
  return { 'X-Device-ID': deviceId, 'X-API-Key': apiKey }
}

export async function fetchDevice(deviceId: string, apiKey: string): Promise<DeviceRecord> {
  const res = await fetch(`${apiBaseUrl}/devices/device/${deviceId}`, {
    headers: deviceAuthHeaders(deviceId, apiKey),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Failed to fetch device (${res.status})`)
  }
  return res.json()
}

export async function fetchDeviceStatus(deviceId: string, apiKey: string): Promise<DeviceStatus> {
  const res = await fetch(`${apiBaseUrl}/agent/${deviceId}/status`, {
    headers: deviceAuthHeaders(deviceId, apiKey),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Failed to fetch status (${res.status})`)
  }
  const json = await res.json()
  return json.data as DeviceStatus
}

export async function fetchPermissions(deviceId: string, apiKey: string): Promise<PermissionsResponse> {
  const res = await fetch(`${apiBaseUrl}/devices/device/${deviceId}/permissions`, {
    headers: deviceAuthHeaders(deviceId, apiKey),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Failed to fetch permissions (${res.status})`)
  }
  return res.json()
}

export async function updatePermissions(
  deviceId: string,
  apiKey: string,
  permissions: Record<string, boolean>,
): Promise<void> {
  const res = await fetch(`${apiBaseUrl}/devices/device/${deviceId}/permissions`, {
    method: 'PATCH',
    headers: { ...deviceAuthHeaders(deviceId, apiKey), 'Content-Type': 'application/json' },
    body: JSON.stringify(permissions),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Failed to update permissions (${res.status})`)
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
    throw new Error(err.detail || `Provision failed (${res.status})`)
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
    throw new Error(err.detail || `Claim failed (${res.status})`)
  }
  const json = await res.json()
  return json.data
}

export async function unpairDevice(deviceId: string, apiKey: string): Promise<void> {
  const res = await fetch(`${apiBaseUrl}/devices/device/${deviceId}/unpair`, {
    method: 'POST',
    headers: { ...deviceAuthHeaders(deviceId, apiKey), 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: 'User-initiated unpair from device settings' }),
  })
  if (!res.ok && res.status !== 404) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Unpair failed (${res.status})`)
  }
}
