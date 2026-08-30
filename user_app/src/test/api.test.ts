import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  fetchDevice,
  fetchDeviceStatus,
  fetchDeviceMetrics,
  fetchPermissions,
  updatePermissions,
  verifyDeviceCredentials,
  bootstrapProvision,
  verifyBootstrapCredentials,
  claimDevice,
  unpairDevice,
  fetchPendingCommands,
  ackCommand,
  updateCommandStatus,
  reportPermissionAudit,
  fetchDeviceLogs,
} from '../services/api'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

const DEVICE_ID = 'test-device'
const API_KEY = 'test-key'

beforeEach(() => {
  mockFetch.mockReset()
})

function ok(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
}

function notFound(detail: string) {
  return Promise.resolve(
    new Response(JSON.stringify({ detail }), { status: 404 }),
  )
}

function serverError(detail: string) {
  return Promise.resolve(
    new Response(JSON.stringify({ detail }), { status: 500 }),
  )
}

describe('fetchDevice', () => {
  it('returns device record on success', async () => {
    const device = { device_id: DEVICE_ID, name: 'Test', lifecycle_state: 'active' }
    mockFetch.mockResolvedValueOnce(ok(device))
    const result = await fetchDevice(DEVICE_ID, API_KEY)
    expect(result.device_id).toBe(DEVICE_ID)
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining(`/devices/device/${DEVICE_ID}`),
      expect.objectContaining({
        headers: { 'X-Device-ID': DEVICE_ID, 'X-API-Key': API_KEY },
      }),
    )
  })

  it('throws on 404', async () => {
    mockFetch.mockResolvedValueOnce(notFound('Device not found'))
    await expect(fetchDevice(DEVICE_ID, API_KEY)).rejects.toThrow('Device not found')
  })

  it('throws on 500', async () => {
    mockFetch.mockResolvedValueOnce(serverError('Server error'))
    await expect(fetchDevice(DEVICE_ID, API_KEY)).rejects.toThrow('Server error')
  })
})

describe('fetchDeviceStatus', () => {
  it('returns status from nested data field', async () => {
    const status = { lifecycle_state: 'active', connectivity_state: 'online', health_state: 'good', last_heartbeat_at: null }
    mockFetch.mockResolvedValueOnce(ok({ data: status }))
    const result = await fetchDeviceStatus(DEVICE_ID, API_KEY)
    expect(result.lifecycle_state).toBe('active')
    expect(result.connectivity_state).toBe('online')
  })

  it('throws on error', async () => {
    mockFetch.mockResolvedValueOnce(notFound('Device not found'))
    await expect(fetchDeviceStatus(DEVICE_ID, API_KEY)).rejects.toThrow('Device not found')
  })
})

describe('fetchDeviceMetrics', () => {
  it('returns metrics from nested data field', async () => {
    const metrics = { cpu_percent: 42, memory_percent: 61, disk_percent: 28, network_latency_ms: 12.5, uptime_seconds: 3725, timestamp: '2026-08-03T12:00:00.000Z' }
    mockFetch.mockResolvedValueOnce(ok({ data: metrics }))
    const result = await fetchDeviceMetrics(DEVICE_ID, API_KEY)
    expect(result.cpu_percent).toBe(42)
    expect(result.memory_percent).toBe(61)
    expect(result.disk_percent).toBe(28)
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining(`/agent/${DEVICE_ID}/metrics`),
      expect.objectContaining({
        headers: { 'X-Device-ID': DEVICE_ID, 'X-API-Key': API_KEY },
      }),
    )
  })

  it('throws on error', async () => {
    mockFetch.mockResolvedValueOnce(serverError('Server error'))
    await expect(fetchDeviceMetrics(DEVICE_ID, API_KEY)).rejects.toThrow('Server error')
  })
})

describe('fetchPendingCommands', () => {
  it('returns pending commands array directly', async () => {
    const commands = [{ command_id: 'c1', command_type: 'request_permission', payload: null, status: 'pending', created_at: '2026-08-03T10:00:00.000Z' }]
    mockFetch.mockResolvedValueOnce(ok(commands))
    const result = await fetchPendingCommands(DEVICE_ID, API_KEY)
    expect(result).toHaveLength(1)
    expect(result[0].command_type).toBe('request_permission')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/devices/pending'),
      expect.objectContaining({
        headers: { 'X-Device-ID': DEVICE_ID, 'X-API-Key': API_KEY },
      }),
    )
  })

  it('throws on error', async () => {
    mockFetch.mockResolvedValueOnce(serverError('Server error'))
    await expect(fetchPendingCommands(DEVICE_ID, API_KEY)).rejects.toThrow('Server error')
  })
})

describe('ackCommand', () => {
  it('POSTs to the ack endpoint', async () => {
    mockFetch.mockResolvedValueOnce(ok({}))
    await ackCommand(DEVICE_ID, API_KEY, 'c1')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining(`/devices/${DEVICE_ID}/commands/c1/ack`),
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('throws on error', async () => {
    mockFetch.mockResolvedValueOnce(serverError('Server error'))
    await expect(ackCommand(DEVICE_ID, API_KEY, 'c1')).rejects.toThrow('Server error')
  })
})

describe('updateCommandStatus', () => {
  it('PUTs status and result', async () => {
    mockFetch.mockResolvedValueOnce(ok({}))
    const result = { permission: 'root_access', action: 'grant', granted: true, message: 'ok' }
    await updateCommandStatus(DEVICE_ID, API_KEY, 'c1', 'completed', result)
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/devices/c1/status'),
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ status: 'completed', result }),
      }),
    )
  })

  it('throws on error', async () => {
    mockFetch.mockResolvedValueOnce(serverError('Server error'))
    await expect(updateCommandStatus(DEVICE_ID, API_KEY, 'c1', 'completed', { permission: 'root_access', action: 'grant', granted: true, message: 'ok' })).rejects.toThrow('Server error')
  })
})

describe('reportPermissionAudit', () => {
  it('POSTs a permission_change audit event', async () => {
    mockFetch.mockResolvedValueOnce(ok({}))
    await reportPermissionAudit(DEVICE_ID, API_KEY, {
      permission: 'root_access',
      granted: true,
      requestedBy: 'admin@example.com',
      action: 'grant',
    })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/agent/audit'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      }),
    )
    const call = mockFetch.mock.calls.find(([, init]) => init?.method === 'POST')
    const body = JSON.parse(String(call![1].body))
    expect(body.event_type).toBe('permission_change')
    expect(body.device_id).toBe(DEVICE_ID)
    expect(body.description).toContain("Permission 'root_access' granted")
  })

  it('throws on error', async () => {
    mockFetch.mockResolvedValueOnce(serverError('Server error'))
    await expect(reportPermissionAudit(DEVICE_ID, API_KEY, { permission: 'root_access', granted: true, requestedBy: 'admin', action: 'grant' })).rejects.toThrow('Server error')
  })
})

describe('fetchDeviceLogs', () => {
  it('returns logs from nested data field', async () => {
    const logs = [{ id: 1, timestamp: '2026-08-03T10:00:00.000Z', category: 'network', severity: 'warning', error_code: null, error_message: 'WAN link flapping detected', resolved: false }]
    mockFetch.mockResolvedValueOnce(ok({ data: logs }))
    const result = await fetchDeviceLogs(DEVICE_ID, API_KEY)
    expect(result).toHaveLength(1)
    expect(result[0].error_message).toBe('WAN link flapping detected')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining(`/agent/${DEVICE_ID}/logs`),
      expect.objectContaining({
        headers: { 'X-Device-ID': DEVICE_ID, 'X-API-Key': API_KEY },
      }),
    )
  })

  it('throws on error', async () => {
    mockFetch.mockResolvedValueOnce(serverError('Server error'))
    await expect(fetchDeviceLogs(DEVICE_ID, API_KEY)).rejects.toThrow('Server error')
  })
})

describe('fetchPermissions', () => {
  it('returns permissions and capabilities from nested data field', async () => {
    const resp = { status: 'success', data: { permissions: { root_access: true }, capabilities: { root_access: true } } }
    mockFetch.mockResolvedValueOnce(ok(resp))
    const result = await fetchPermissions(DEVICE_ID, API_KEY)
    expect(result.permissions.root_access).toBe(true)
    expect(result.capabilities.root_access).toBe(true)
  })
})

describe('updatePermissions', () => {
  it('sends PATCH with permissions wrapped in body', async () => {
    mockFetch.mockResolvedValueOnce(ok({}))
    await updatePermissions(DEVICE_ID, API_KEY, { root_access: true })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining(`/devices/device/${DEVICE_ID}/permissions`),
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ permissions: { root_access: true } }),
      }),
    )
  })

  it('throws on error', async () => {
    mockFetch.mockResolvedValueOnce(serverError('Update failed'))
    await expect(updatePermissions(DEVICE_ID, API_KEY, {})).rejects.toThrow('Update failed')
  })
})

describe('bootstrapProvision', () => {
  it('POSTs provision request and returns data', async () => {
    const resp = { data: { device_id: 'd1', api_key: 'k1', site_id: 's1' } }
    mockFetch.mockResolvedValueOnce(ok(resp))
    const result = await bootstrapProvision({
      site_id: 's1',
      device_name: 'Test',
      device_type: 'pos_terminal',
      os_details: 'linux',
      bootstrap_key: 'bk-123',
    })
    expect(result.device_id).toBe('d1')
    expect(result.api_key).toBe('k1')
  })
})

describe('verifyBootstrapCredentials', () => {
  it('POSTs the Site ID/key pair and returns the generic result', async () => {
    mockFetch.mockResolvedValueOnce(ok({ data: { verified: true } }))
    await expect(verifyBootstrapCredentials({
      site_id: 'site-001',
      bootstrap_key: 'bk-123',
    })).resolves.toEqual({ verified: true })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/devices/verify-bootstrap'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ site_id: 'site-001', bootstrap_key: 'bk-123' }),
      }),
    )
  })

  it('throws when verification is unavailable', async () => {
    mockFetch.mockResolvedValueOnce(serverError('Unavailable'))
    await expect(verifyBootstrapCredentials({
      site_id: 'site-001',
      bootstrap_key: 'bk-123',
    })).rejects.toThrow('Unavailable')
  })
})

describe('claimDevice', () => {
  it('POSTs claim request and returns flat result', async () => {
    const resp = { status: 'success', device_id: 'd2', api_key: 'k2', site_id: 's2', epoch_id: 'e2' }
    mockFetch.mockResolvedValueOnce(ok(resp))
    const result = await claimDevice({
      intent_id: 'intent-1',
      claim_token: 'token-1',
      device_name: 'Test',
      device_type: 'pos_terminal',
      os_details: 'linux',
    })
    expect(result.device_id).toBe('d2')
    expect(result.api_key).toBe('k2')
    expect(result.site_id).toBe('s2')
  })
})

describe('unpairDevice', () => {
  it('sends POST and returns a confirmed ack on 200', async () => {
    mockFetch.mockResolvedValueOnce(
      ok({
        status: 'success',
        message: 'ok',
        device_id: DEVICE_ID,
        lifecycle_state: 'unpaired',
        connectivity_state: 'offline',
        disconnected_at: '2026-08-03T12:34:56.000Z',
        confirmed: true,
      }),
    )
    const ack = await unpairDevice(DEVICE_ID, API_KEY)
    expect(ack.confirmed).toBe(true)
    expect(ack.lifecycle_state).toBe('unpaired')
    expect(ack.connectivity_state).toBe('offline')
  })

  it('does not confirm when the response lacks an unpaired lifecycle', async () => {
    mockFetch.mockResolvedValueOnce(ok({}))
    const ack = await unpairDevice(DEVICE_ID, API_KEY)
    expect(ack.confirmed).toBe(false)
  })

  it('sends POST with reason and idempotency key', async () => {
    mockFetch.mockResolvedValueOnce(
      ok({
        status: 'success',
        message: 'ok',
        device_id: DEVICE_ID,
        lifecycle_state: 'unpaired',
        connectivity_state: 'offline',
      }),
    )
    await unpairDevice(DEVICE_ID, API_KEY, {
      reason: 'Upgrade',
      idempotencyKey: 'unpair-x',
    })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining(`/devices/device/${DEVICE_ID}/unpair`),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ reason: 'Upgrade', idempotency_key: 'unpair-x' }),
      }),
    )
  })

  it('succeeds on 404 (device already unpaired)', async () => {
    mockFetch.mockResolvedValueOnce(notFound('Device not found'))
    const ack = await unpairDevice(DEVICE_ID, API_KEY)
    expect(ack.confirmed).toBe(true)
  })

  it('throws on 500', async () => {
    mockFetch.mockResolvedValueOnce(serverError('Server error'))
    await expect(unpairDevice(DEVICE_ID, API_KEY)).rejects.toThrow('Server error')
  })
})

describe('verifyDeviceCredentials', () => {
  it('returns true when credentials are accepted', async () => {
    mockFetch.mockResolvedValueOnce(
      ok({ data: { permissions: { root_access: true }, capabilities: { root_access: true } } }),
    )
    await expect(verifyDeviceCredentials(DEVICE_ID, API_KEY)).resolves.toBe(true)
  })

  it('returns false on 401 (invalid device ID)', async () => {
    mockFetch.mockResolvedValueOnce(
      Promise.resolve(new Response(JSON.stringify({ detail: 'Invalid Device ID' }), { status: 401 })),
    )
    await expect(verifyDeviceCredentials(DEVICE_ID, API_KEY)).resolves.toBe(false)
  })

  it('returns false on 401 (invalid API key)', async () => {
    mockFetch.mockResolvedValueOnce(
      Promise.resolve(new Response(JSON.stringify({ detail: 'Invalid API Key' }), { status: 401 })),
    )
    await expect(verifyDeviceCredentials(DEVICE_ID, API_KEY)).resolves.toBe(false)
  })

  it('returns true on 403 (suspended device, creds still valid)', async () => {
    mockFetch.mockResolvedValueOnce(
      Promise.resolve(new Response(JSON.stringify({ detail: "device is in lifecycle state 'suspended'" }), { status: 403 })),
    )
    await expect(verifyDeviceCredentials(DEVICE_ID, API_KEY)).resolves.toBe(true)
  })

  it('returns true on network error (do not clear creds offline)', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'))
    await expect(verifyDeviceCredentials(DEVICE_ID, API_KEY)).resolves.toBe(true)
  })
})
