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

export interface PendingCommand {
  command_id: string
  command_type: string
  payload: Record<string, unknown> | null
  status: string
  created_at: string
}

export interface PermissionRequestResult {
  permission: string
  action: string
  granted: boolean
  message: string
}

export interface DeviceLog {
  id: number
  timestamp: string | null
  category: string
  severity: string
  error_code: string | null
  error_message: string
  resolved: boolean
}

export interface AuditEvent {
  id: number
  event_type: string
  description: string
  created_at: string | null
  ip_address: string | null
  metadata: Record<string, unknown> | null
}

export interface DeviceJob {
  job_id: string
  action: string
  description: string | null
  status: string
  priority: string
  created_at: string | null
  completed_at: string | null
  result: Record<string, unknown> | null
  error_message: string | null
}

export interface DeviceAlert {
  id: number
  title: string
  description: string | null
  severity: string
  category: string
  status: string
  timestamp: string | null
  ai_recommendation: string | null
  ai_confidence: number | null
}

export interface PushHistoryEntry {
  id: number
  timestamp: string | null
  parameter_name: string
  old_value: Record<string, unknown> | null
  new_value: Record<string, unknown> | null
  change_reason: string | null
  changed_by: string
  was_successful: boolean | null
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

export async function fetchPendingCommands(
  deviceId: string,
  apiKey: string,
): Promise<PendingCommand[]> {
  const res = await fetch(`${apiBaseUrl}/devices/pending`, {
    headers: deviceAuthHeaders(deviceId, apiKey),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw asApiError(body.detail || `Failed to fetch pending commands (${res.status})`, res.status)
  }
  return res.json()
}

export async function ackCommand(
  deviceId: string,
  apiKey: string,
  commandId: string,
): Promise<void> {
  const res = await fetch(`${apiBaseUrl}/devices/${deviceId}/commands/${commandId}/ack`, {
    method: 'POST',
    headers: deviceAuthHeaders(deviceId, apiKey),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw asApiError(body.detail || `Failed to acknowledge command (${res.status})`, res.status)
  }
}

export async function updateCommandStatus(
  deviceId: string,
  apiKey: string,
  commandId: string,
  status: string,
  result: PermissionRequestResult,
): Promise<void> {
  const res = await fetch(`${apiBaseUrl}/devices/${commandId}/status`, {
    method: 'PUT',
    headers: { ...deviceAuthHeaders(deviceId, apiKey), 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, result }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw asApiError(body.detail || `Failed to update command status (${res.status})`, res.status)
  }
}

export async function reportPermissionAudit(
  deviceId: string,
  apiKey: string,
  payload: {
    permission: string
    granted: boolean
    requestedBy: string
    action: string
  },
): Promise<void> {
  const verb = payload.granted ? 'granted' : 'denied'
  const res = await fetch(`${apiBaseUrl}/agent/audit`, {
    method: 'POST',
    headers: { ...deviceAuthHeaders(deviceId, apiKey), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      device_id: deviceId,
      event_type: 'permission_change',
      description: `Permission '${payload.permission}' ${verb} (${payload.action}) by ${payload.requestedBy}`,
      timestamp: new Date().toISOString(),
    }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw asApiError(body.detail || `Failed to report audit event (${res.status})`, res.status)
  }
}

async function fetchDeviceActivity<T>(
  deviceId: string,
  apiKey: string,
  resource: string,
  label: string,
): Promise<T[]> {
  const res = await fetch(`${apiBaseUrl}/agent/${deviceId}/${resource}`, {
    headers: deviceAuthHeaders(deviceId, apiKey),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw asApiError(body.detail || `Failed to fetch ${label} (${res.status})`, res.status)
  }
  const json = await res.json()
  return json.data as T[]
}

export function fetchDeviceLogs(
  deviceId: string,
  apiKey: string,
): Promise<DeviceLog[]> {
  return fetchDeviceActivity<DeviceLog>(deviceId, apiKey, 'logs', 'logs')
}

export function fetchAuditEvents(
  deviceId: string,
  apiKey: string,
): Promise<AuditEvent[]> {
  return fetchDeviceActivity<AuditEvent>(deviceId, apiKey, 'audit', 'audit events')
}

export function fetchDeviceJobs(
  deviceId: string,
  apiKey: string,
): Promise<DeviceJob[]> {
  return fetchDeviceActivity<DeviceJob>(deviceId, apiKey, 'jobs', 'jobs')
}

export function fetchDeviceAlerts(
  deviceId: string,
  apiKey: string,
): Promise<DeviceAlert[]> {
  return fetchDeviceActivity<DeviceAlert>(deviceId, apiKey, 'alerts', 'alerts')
}

export function fetchPushHistory(
  deviceId: string,
  apiKey: string,
): Promise<PushHistoryEntry[]> {
  return fetchDeviceActivity<PushHistoryEntry>(deviceId, apiKey, 'push-history', 'push history')
}
