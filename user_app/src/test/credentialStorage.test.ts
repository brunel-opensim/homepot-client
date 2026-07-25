import { describe, it, expect, beforeEach } from 'vitest'
import { SimulationStorage } from '../services/credentialStorage'

describe('SimulationStorage', () => {
  let storage: SimulationStorage

  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    storage = new SimulationStorage()
  })

  it('isProvisioned returns false when no credentials exist', async () => {
    expect(await storage.isProvisioned()).toBe(false)
  })

  it('save stores credentials and isProvisioned returns true', async () => {
    await storage.save({
      deviceId: 'test-device-001',
      apiKey: 'test-api-key',
      siteId: 'site-001',
      deviceName: 'Test Device',
      deviceType: 'pos_terminal',
      deviceOs: 'linux',
    })
    expect(await storage.isProvisioned()).toBe(true)
    expect(await storage.getDeviceId()).toBe('test-device-001')
    expect(await storage.getApiKey()).toBe('test-api-key')
  })

  it('save stores optional metadata fields', async () => {
    await storage.save({
      deviceId: 'd1',
      apiKey: 'k1',
      siteId: 's1',
      deviceName: 'My POS',
      deviceType: 'pos_terminal',
      deviceOs: 'windows',
      enrollmentMethod: 'self-enrolled',
    })
    expect(await storage.getMetadata('site_id')).toBe('s1')
    expect(await storage.getMetadata('device_name')).toBe('My POS')
    expect(await storage.getMetadata('device_type')).toBe('pos_terminal')
    expect(await storage.getMetadata('device_os')).toBe('windows')
    expect(await storage.getMetadata('enrollment_method')).toBe('self-enrolled')
  })

  it('save stores empty strings for missing optional fields', async () => {
    await storage.save({ deviceId: 'd2', apiKey: 'k2' })
    expect(await storage.getMetadata('device_name')).toBe('')
    expect(await storage.getMetadata('device_type')).toBe('')
    expect(await storage.getMetadata('device_os')).toBe('')
  })

  it('getDeviceId returns null when not provisioned', async () => {
    expect(await storage.getDeviceId()).toBeNull()
  })

  it('getApiKey returns null when not provisioned', async () => {
    expect(await storage.getApiKey()).toBeNull()
  })

  it('getMetadata returns null for unknown key', async () => {
    expect(await storage.getMetadata('nonexistent')).toBeNull()
  })

  it('clear removes all credentials', async () => {
    await storage.save({ deviceId: 'd3', apiKey: 'k3' })
    expect(await storage.isProvisioned()).toBe(true)
    await storage.clear()
    expect(await storage.isProvisioned()).toBe(false)
    expect(await storage.getDeviceId()).toBeNull()
    expect(await storage.getApiKey()).toBeNull()
  })

  it('clear does not affect unrelated localStorage keys', async () => {
    localStorage.setItem('other_key', 'keep-me')
    await storage.save({ deviceId: 'd4', apiKey: 'k4' })
    await storage.clear()
    expect(localStorage.getItem('other_key')).toBe('keep-me')
  })

  it('api key is stored in sessionStorage (cleared on tab close)', async () => {
    await storage.save({ deviceId: 'd5', apiKey: 'secret-key' })
    expect(sessionStorage.getItem('homepot_api_key')).toBe('secret-key')
    expect(localStorage.getItem('homepot_device_id')).toBe('d5')
  })

  it('multiple saves overwrite previous values', async () => {
    await storage.save({ deviceId: 'first', apiKey: 'key-a' })
    await storage.save({ deviceId: 'second', apiKey: 'key-b' })
    expect(await storage.getDeviceId()).toBe('second')
    expect(await storage.getApiKey()).toBe('key-b')
  })

  it('handles concurrent saves gracefully', async () => {
    const promises = Array.from({ length: 10 }, (_, i) =>
      storage.save({ deviceId: `d${i}`, apiKey: `k${i}` }),
    )
    await Promise.all(promises)
    const deviceId = await storage.getDeviceId()
    const apiKey = await storage.getApiKey()
    expect(deviceId).toMatch(/^d\d$/)
    expect(apiKey).toMatch(/^k\d$/)
  })
})
