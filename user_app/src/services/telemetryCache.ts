import type { DeviceStatus, DeviceMetrics } from './api'

/**
 * Lightweight in-memory telemetry cache for the User App.
 *
 * Holds only the last-fetched status + metrics for the current device so page
 * navigations render instantly (no disk, no large payloads). Cleared on unpair
 * so a re-enrolled device never shows stale data.
 */
interface TelemetrySnapshot {
  status: DeviceStatus | null
  metrics: DeviceMetrics | null
  updatedAt: number
}

const cache = new Map<string, TelemetrySnapshot>()

export function getCachedTelemetry(deviceId: string): TelemetrySnapshot | undefined {
  return cache.get(deviceId)
}

export function setCachedTelemetry(
  deviceId: string,
  status: DeviceStatus | null,
  metrics: DeviceMetrics | null,
): void {
  cache.set(deviceId, { status, metrics, updatedAt: Date.now() })
}

export function clearCachedTelemetry(deviceId: string): void {
  cache.delete(deviceId)
}