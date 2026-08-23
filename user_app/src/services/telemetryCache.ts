import type { DeviceStatus, DeviceMetrics, DeviceRecord } from './api'

/**
 * Lightweight in-memory telemetry cache for the User App.
 *
 * Holds only the last-fetched status + metrics + device record for the
 * current device so page navigations render instantly (no disk, no large
 * payloads). Cleared on unpair so a re-enrolled device never shows stale data.
 */
interface TelemetrySnapshot {
  status: DeviceStatus | null
  metrics: DeviceMetrics | null
  device: DeviceRecord | null
  updatedAt: number
}

const cache = new Map<string, TelemetrySnapshot>()

export function getCachedTelemetry(deviceId: string): TelemetrySnapshot | undefined {
  return cache.get(deviceId)
}

export function getCachedDevice(deviceId: string): DeviceRecord | null {
  return cache.get(deviceId)?.device ?? null
}

export function setCachedTelemetry(
  deviceId: string,
  status: DeviceStatus | null,
  metrics: DeviceMetrics | null,
): void {
  const existing = cache.get(deviceId)
  cache.set(deviceId, {
    status,
    metrics,
    device: existing?.device ?? null,
    updatedAt: Date.now(),
  })
}

export function setCachedDevice(deviceId: string, device: DeviceRecord): void {
  const existing = cache.get(deviceId)
  cache.set(deviceId, {
    status: existing?.status ?? null,
    metrics: existing?.metrics ?? null,
    device,
    updatedAt: Date.now(),
  })
}

export function clearCachedTelemetry(deviceId: string): void {
  cache.delete(deviceId)
}

export function clearAllCachedTelemetry(): void {
  cache.clear()
}