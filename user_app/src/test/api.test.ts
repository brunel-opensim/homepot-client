import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  fetchDevice,
  fetchDeviceStatus,
  fetchPermissions,
  updatePermissions,
  bootstrapProvision,
  claimDevice,
  unpairDevice,
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

describe('fetchPermissions', () => {
  it('returns permissions and capabilities', async () => {
    const resp = { permissions: { root_access: true }, capabilities: { root_access: true } }
    mockFetch.mockResolvedValueOnce(ok(resp))
    const result = await fetchPermissions(DEVICE_ID, API_KEY)
    expect(result.permissions.root_access).toBe(true)
    expect(result.capabilities.root_access).toBe(true)
  })
})

describe('updatePermissions', () => {
  it('sends PATCH with correct body', async () => {
    mockFetch.mockResolvedValueOnce(ok({}))
    await updatePermissions(DEVICE_ID, API_KEY, { root_access: true })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining(`/devices/device/${DEVICE_ID}/permissions`),
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ root_access: true }),
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

describe('claimDevice', () => {
  it('POSTs claim request and returns data', async () => {
    const resp = { data: { device_id: 'd2', api_key: 'k2', site_id: 's2' } }
    mockFetch.mockResolvedValueOnce(ok(resp))
    const result = await claimDevice({
      intent_id: 'intent-1',
      claim_token: 'token-1',
      device_name: 'Test',
      device_type: 'pos_terminal',
      os_details: 'linux',
    })
    expect(result.device_id).toBe('d2')
  })
})

describe('unpairDevice', () => {
  it('sends POST and succeeds on 200', async () => {
    mockFetch.mockResolvedValueOnce(ok({}))
    await expect(unpairDevice(DEVICE_ID, API_KEY)).resolves.toBeUndefined()
  })

  it('succeeds on 404 (device already unpaired)', async () => {
    mockFetch.mockResolvedValueOnce(notFound('Device not found'))
    await expect(unpairDevice(DEVICE_ID, API_KEY)).resolves.toBeUndefined()
  })

  it('throws on 500', async () => {
    mockFetch.mockResolvedValueOnce(serverError('Server error'))
    await expect(unpairDevice(DEVICE_ID, API_KEY)).rejects.toThrow('Server error')
  })
})
