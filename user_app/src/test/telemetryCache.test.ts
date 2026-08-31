import { describe, it, expect, beforeEach } from 'vitest'
import {
  getCachedTelemetry,
  getCachedDevice,
  setCachedTelemetry,
  setCachedDevice,
  clearCachedTelemetry,
  clearAllCachedTelemetry,
} from '../services/telemetryCache'
import type { DeviceRecord, DeviceStatus, DeviceMetrics } from '../services/api'

const status: DeviceStatus = {
  lifecycle_state: 'provisioned',
  connectivity_state: 'online',
  health_state: 'healthy',
  last_heartbeat_at: '2026-08-31T12:00:00Z',
}
const metrics: DeviceMetrics = {
  cpu_percent: 10,
  memory_percent: 20,
  disk_percent: 30,
  network_latency_ms: 12,
  uptime_seconds: 3600,
  timestamp: '2026-08-31T12:00:00Z',
}
const device: DeviceRecord = {
  site_id: 'site-1',
  site_name: 'Site One',
  device_id: 'dev-1',
  name: 'Kitchen POS',
  device_type: 'pos_terminal',
  lifecycle_state: 'provisioned',
  connectivity_state: 'online',
  health_state: 'healthy',
  mac_address: 'aa:bb:cc:dd:ee:ff',
  local_ip: '192.168.1.10',
  wan_ip: '203.0.113.5',
  os_details: 'Linux 6.8.0',
  firmware_version: '0.1.0',
  last_seen: '2026-08-31T12:00:00Z',
  last_heartbeat_at: '2026-08-31T12:00:00Z',
  credential_status: 'claimed',
  device_permissions: {},
  capabilities: {},
}

describe('telemetryCache', () => {
  beforeEach(() => {
    clearAllCachedTelemetry()
  })

  it('returns undefined when nothing is cached for a device', () => {
    expect(getCachedTelemetry('dev-unknown')).toBeUndefined()
    expect(getCachedDevice('dev-unknown')).toBeNull()
  })

  it('setCachedTelemetry stores status and metrics', () => {
    setCachedTelemetry('dev-1', status, metrics)
    const snap = getCachedTelemetry('dev-1')
    expect(snap?.status).toBe(status)
    expect(snap?.metrics).toBe(metrics)
    expect(snap?.device).toBeNull()
    expect(snap?.updatedAt).toBeGreaterThan(0)
  })

  it('setCachedDevice stores the device record', () => {
    setCachedDevice('dev-1', device)
    expect(getCachedDevice('dev-1')).toBe(device)
    expect(getCachedTelemetry('dev-1')?.device).toBe(device)
  })

  it('setCachedTelemetry preserves a previously cached device record', () => {
    setCachedDevice('dev-1', device)
    setCachedTelemetry('dev-1', status, metrics)
    expect(getCachedTelemetry('dev-1')?.device).toBe(device)
    expect(getCachedTelemetry('dev-1')?.status).toBe(status)
  })

  it('setCachedDevice preserves previously cached status and metrics', () => {
    setCachedTelemetry('dev-1', status, metrics)
    const newDevice = { ...device, name: 'Renamed' } as DeviceRecord
    setCachedDevice('dev-1', newDevice)
    const snap = getCachedTelemetry('dev-1')
    expect(snap?.device).toBe(newDevice)
    expect(snap?.status).toBe(status)
    expect(snap?.metrics).toBe(metrics)
  })

  it('clearCachedTelemetry removes only the given device', () => {
    setCachedTelemetry('dev-1', status, metrics)
    setCachedTelemetry('dev-2', status, metrics)
    clearCachedTelemetry('dev-1')
    expect(getCachedTelemetry('dev-1')).toBeUndefined()
    expect(getCachedTelemetry('dev-2')).not.toBeUndefined()
  })

  it('clearAllCachedTelemetry wipes every cached snapshot', () => {
    setCachedTelemetry('dev-1', status, metrics)
    setCachedTelemetry('dev-2', status, metrics)
    clearAllCachedTelemetry()
    expect(getCachedTelemetry('dev-1')).toBeUndefined()
    expect(getCachedTelemetry('dev-2')).toBeUndefined()
  })

  it('setCachedTelemetry with null status/metrics stores nulls', () => {
    setCachedTelemetry('dev-1', null, null)
    const snap = getCachedTelemetry('dev-1')
    expect(snap?.status).toBeNull()
    expect(snap?.metrics).toBeNull()
  })
})
