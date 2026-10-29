import { useState, useEffect, useRef } from 'react'
import TabBar from '../components/TabBar'
import GaugeRing from '../components/GaugeRing'
import MetricsHistoryChart from '../components/MetricsHistoryChart'
import { credentialStorage } from '../services/credentialStorage'
import { fetchDeviceStatus, fetchDeviceMetrics, fetchDeviceMetricsHistory, fetchPermissions } from '../services/api'
import { getCachedTelemetry, setCachedTelemetry } from '../services/telemetryCache'
import { MANAGE_KEY, MONITOR_KEYS } from '../services/permissionsEvents'
import type { DeviceStatus, DeviceMetrics } from '../services/api'

function formatUptime(totalSeconds: number | null): string {
  if (totalSeconds === null || totalSeconds === undefined) return '—'
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  if (hours === 0) return `${minutes}m`
  return `${hours}h ${minutes}m`
}

function formatHeartbeat(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return '—'
  }
}

// Radar-ping "connecting" indicator: concentric rings expand outward from a
// solid centre dot, like a sonar ping. Honest — it signals "searching" without
// implying fake intermediate stages.
function RadarPing() {
  return (
    <span className="relative inline-flex h-5 w-5 items-center justify-center">
      <span className="absolute inline-flex h-full w-full rounded-full bg-amber-400/30 animate-ping" />
      <span className="absolute inline-flex h-3 w-3 rounded-full bg-amber-400/40 animate-ping [animation-delay:300ms]" />
      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-amber-400" />
    </span>
  )
}

// Real, honest connection checklist — each step lights up only when the
// corresponding signal has actually arrived from the backend.
function ConnectionChecklist({
  deviceId,
  status,
  connectivity,
}: {
  deviceId: string | null
  status: DeviceStatus | null
  connectivity: string
}) {
  const steps = [
    { label: 'Device enrolled', done: !!deviceId },
    { label: 'Agent reporting', done: status !== null },
    { label: 'First heartbeat', done: connectivity === 'online' },
  ]
  return (
    <div className="px-5 pt-2">
      <div className="rounded-xl border border-amber-900/60 bg-amber-950/40 p-3 space-y-1.5">
        {steps.map((step) => (
          <div key={step.label} className="flex items-center gap-2 text-xs">
            <span
              className={
                step.done
                  ? 'text-emerald-400 font-bold'
                  : 'text-amber-400/60'
              }
            >
              {step.done ? '✓' : '⋯'}
            </span>
            <span
              className={
                step.done
                  ? 'text-slate-200'
                  : 'text-slate-500'
              }
            >
              {step.label}
            </span>
            {!step.done && step.label === 'First heartbeat' && (
              <span className="ml-auto text-[10px] text-amber-400/70 animate-pulse">
                waiting…
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// Pick a device-representing icon for the header, based on the device type.
function deviceEmoji(deviceType: string | null): string {
  const t = (deviceType || '').toLowerCase()
  if (t.includes('tablet')) return '📱'
  if (t.includes('scanner') || t.includes('mobile')) return '📟'
  if (t.includes('kiosk')) return '🖥️'
  if (t.includes('virtual')) return '💻'
  return '🖥️' // pos_terminal and default
}

export default function HomeDashboard() {
  const [deviceName, setDeviceName] = useState('My Device')
  const [deviceId, setDeviceId] = useState<string | null>(null)
  const [deviceType, setDeviceType] = useState<string | null>(null)
  const [status, setStatus] = useState<DeviceStatus | null>(null)
  const [metrics, setMetrics] = useState<DeviceMetrics | null>(null)
  const [history, setHistory] = useState<DeviceMetrics[]>([])
  const [devicePermissions, setDevicePermissions] = useState<Record<string, boolean> | null>(null)
  const deviceIdRef = useRef<string | null>(null)
  const apiKeyRef = useRef<string | null>(null)

  useEffect(() => {
    Promise.all([
      credentialStorage.getDeviceId(),
      credentialStorage.getApiKey(),
      credentialStorage.getMetadata('device_name'),
      credentialStorage.getMetadata('device_type'),
    ]).then(([did, key, name, type]) => {
      if (did) { setDeviceId(did); deviceIdRef.current = did }
      if (key) apiKeyRef.current = key
      if (name) setDeviceName(name)
      if (type) setDeviceType(type)
    })
  }, [])

  useEffect(() => {
    async function fetchStatus() {
      const dId = deviceIdRef.current
      const aKey = apiKeyRef.current
      if (!dId || !aKey) return
      try {
        const fresh = await fetchDeviceStatus(dId, aKey)
        setStatus(fresh)
        const cached = getCachedTelemetry(dId)
        setCachedTelemetry(dId, fresh, cached?.metrics ?? null)
      } catch {
        // silently degrade
      }
    }
    async function fetchMetrics() {
      const dId = deviceIdRef.current
      const aKey = apiKeyRef.current
      if (!dId || !aKey) return
      try {
        const fresh = await fetchDeviceMetrics(dId, aKey)
        setMetrics(fresh)
        const cached = getCachedTelemetry(dId)
        setCachedTelemetry(dId, cached?.status ?? null, fresh)
      } catch {
        // silently degrade
      }
    }
    async function fetchHistory() {
      const dId = deviceIdRef.current
      const aKey = apiKeyRef.current
      if (!dId || !aKey) return
      try {
        const samples = await fetchDeviceMetricsHistory(dId, aKey, 60)
        setHistory(Array.isArray(samples) ? samples : [])
      } catch {
        // silently degrade
      }
    }
    async function fetchPermissionsData() {
      const dId = deviceIdRef.current
      const aKey = apiKeyRef.current
      if (!dId || !aKey) return
      try {
        const res = await fetchPermissions(dId, aKey)
        setDevicePermissions(res.permissions)
      } catch {
        // silently degrade
      }
    }
    if (!deviceIdRef.current || !apiKeyRef.current) return

    // Render any cached telemetry immediately, then refresh from the backend.
    const dId = deviceIdRef.current
    const cached = getCachedTelemetry(dId)
    if (cached) {
      if (cached.status) setStatus(cached.status)
      if (cached.metrics) setMetrics(cached.metrics)
    }

    // Poll status aggressively right after mount so the CONNECTING -> ONLINE
    // transition is noticed within ~2s instead of up to 30s; back off to 30s
    // once the device reports online (or after 30s regardless).
    const fastPollingRef = { current: true }
    const statusIntervalRef = { current: null as ReturnType<typeof setInterval> | null }
    const scheduleStatus = (delay: number) => {
      if (statusIntervalRef.current) clearInterval(statusIntervalRef.current)
      statusIntervalRef.current = setInterval(async () => {
        await fetchStatus()
      }, delay)
    }

    // Poll metrics aggressively right after mount too, so CPU/Memory/Disk/
    // Network/Uptime appear within ~2s instead of up to 15s. Back off to 15s
    // after 30s.
    const metricsIntervalRef = { current: null as ReturnType<typeof setInterval> | null }
    const scheduleMetrics = (delay: number) => {
      if (metricsIntervalRef.current) clearInterval(metricsIntervalRef.current)
      metricsIntervalRef.current = setInterval(fetchMetrics, delay)
    }

    fetchStatus()
    fetchMetrics()
    fetchHistory()
    fetchPermissionsData()
    scheduleStatus(2000)
    scheduleMetrics(2000)
    const statusSlowdown = setTimeout(() => {
      fastPollingRef.current = false
      scheduleStatus(30000)
    }, 30000)
    const metricsSlowdown = setTimeout(() => {
      scheduleMetrics(15000)
    }, 30000)
    const historyIntervalRef = { current: null as ReturnType<typeof setInterval> | null }
    const scheduleHistory = (delay: number) => {
      if (historyIntervalRef.current) clearInterval(historyIntervalRef.current)
      historyIntervalRef.current = setInterval(fetchHistory, delay)
    }
    scheduleHistory(5000)
    const historySlowdown = setTimeout(() => {
      scheduleHistory(30000)
    }, 30000)
    const permissionsInterval = setInterval(fetchPermissionsData, 30000)
    return () => {
      if (statusIntervalRef.current) clearInterval(statusIntervalRef.current)
      if (metricsIntervalRef.current) clearInterval(metricsIntervalRef.current)
      if (historyIntervalRef.current) clearInterval(historyIntervalRef.current)
      clearTimeout(statusSlowdown)
      clearTimeout(metricsSlowdown)
      clearTimeout(historySlowdown)
      clearInterval(permissionsInterval)
    }
  }, [deviceId])

  const connectivity = status?.connectivity_state || 'unknown'
  const lifecycle = status?.lifecycle_state || 'unknown'
  const isOnline = connectivity === 'online'
  const isOffline = connectivity === 'offline'
  // 'unknown' (no heartbeat yet — e.g. right after provisioning) renders as
  // CONNECTING instead of alarming red OFFLINE.
  const isConnecting = !isOnline && !isOffline

  // Prompt the owner to grant access until both tiers are granted. Until then
  // no telemetry flows, so the CPU/Memory/Disk gauges stay empty.
  const monitorGranted =
    !!devicePermissions && MONITOR_KEYS.every((k) => devicePermissions[k] === true)
  const manageGranted = !!devicePermissions && devicePermissions[MANAGE_KEY] === true
  const showAccessPrompt = isOnline && !(monitorGranted && manageGranted)

  const statusStyles = isOnline
    ? {
        card: 'bg-emerald-950 border border-emerald-800',
        circle: 'border-emerald-400 bg-emerald-900',
        text: 'text-emerald-400',
        glyph: '✓',
        label: 'SECURE — ONLINE',
        dot: 'bg-emerald-400 animate-pulse',
      }
    : isConnecting
      ? {
          card: 'bg-amber-950 border border-amber-800',
          circle: 'border-amber-400 bg-amber-900',
          text: 'text-amber-400',
          glyph: '⋯',
          label: 'CONNECTING…',
          dot: 'bg-amber-400 animate-pulse',
        }
      : {
          card: 'bg-red-950 border border-red-800',
          circle: 'border-red-400 bg-red-900',
          text: 'text-red-400',
          glyph: '✕',
          label: 'OFFLINE',
          dot: 'bg-red-500',
        }
  const cpu = metrics?.cpu_percent ?? 0
  const mem = metrics?.memory_percent ?? 0
  const disk = metrics?.disk_percent ?? 0

  if (lifecycle === 'unpaired' || lifecycle === 'retired') {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
        <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 p-8 text-center">
          <p className="text-red-400 font-bold text-lg">Device {lifecycle}</p>
          <p className="text-slate-400 text-sm mt-2">This device is no longer active. Please re-enrol.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 flex flex-col overflow-hidden">
    
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-slate-700">
          <div>
            <h1 className="text-slate-100 font-bold text-base tracking-wide">HOMEPOT Agent</h1>
            <p className="text-slate-500 text-xs">Digital Security Badge</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-300 text-sm font-medium">{deviceName}</span>
            <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-base">
              {deviceEmoji(deviceType)}
            </div>
          </div>
        </div>

        {/* Status Badge */}
        <div className="px-5 pt-4">
          <div className={`w-full rounded-xl p-4 flex items-center gap-3 ${statusStyles.card}`}>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 flex-shrink-0 ${statusStyles.circle}`}>
              <span className={`text-lg font-bold flex items-center ${statusStyles.text}`}>
                {isConnecting ? <RadarPing /> : statusStyles.glyph}
              </span>
            </div>
            <div>
              <p className={`font-bold text-sm ${statusStyles.text}`}>
                {statusStyles.label}
              </p>
              {showAccessPrompt && (
                <p className="text-[11px] text-emerald-100/80 mt-0.5 leading-snug">
                  Grant Monitor &amp; Manage access from the Perms page to enable telemetry.
                </p>
              )}
            </div>
            <div className={`ml-auto w-2 h-2 rounded-full flex-shrink-0 ${statusStyles.dot}`} />
          </div>
        </div>

        {isConnecting && (
          <ConnectionChecklist
            deviceId={deviceId}
            status={status}
            connectivity={connectivity}
          />
        )}

        {/* Suspended banner */}
        {lifecycle === 'suspended' && (
          <div className="px-5 pt-3">
            <div className="bg-orange-950 border border-orange-800 rounded-xl p-3 text-center">
              <p className="text-orange-400 text-xs font-medium">DEVICE SUSPENDED</p>
              <p className="text-orange-300 text-xs mt-1">Contact your administrator to resume service.</p>
            </div>
          </div>
        )}

        {/* Gauge Rings */}
        <div className="px-5 pt-5">
          <p className="text-slate-500 text-xs font-medium mb-3 uppercase tracking-widest">Device Resource Usage</p>
          <div className="flex justify-around">
            <GaugeRing label="CPU" value={cpu} color="#10b981" />
            <GaugeRing label="Memory" value={mem} color="#f59e0b" />
            <GaugeRing label="Disk" value={disk} color="#3b82f6" />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <div className="bg-slate-700 rounded-lg px-3 py-2 flex items-center justify-between">
              <span className="text-slate-400 text-xs">Network</span>
              <span className="text-slate-200 text-xs font-mono">
                {metrics?.network_latency_ms != null ? `${metrics.network_latency_ms.toFixed(1)}ms` : '—'}
              </span>
            </div>
            <div className="bg-slate-700 rounded-lg px-3 py-2 flex items-center justify-between">
              <span className="text-slate-400 text-xs">Uptime</span>
              <span className="text-slate-200 text-xs font-mono">{formatUptime(metrics?.uptime_seconds ?? null)}</span>
            </div>
          </div>
        </div>

        {/* History charts */}
        {(() => {
          // Merge current metrics into history so the graph's last point
          // matches the live reading.  Without this the graph lags behind
          // the reading by up to one poll cycle and can look "empty" on first
          // load because history arrives after metrics.
          const mergedHistory = Array.isArray(history) ? [...history] : []
          if (metrics && mergedHistory.length > 0) {
            const last = mergedHistory[mergedHistory.length - 1]
            // Only append if the current metric is newer than the last history sample
            if (!last.timestamp || !metrics.timestamp || new Date(metrics.timestamp) > new Date(last.timestamp)) {
              mergedHistory.push(metrics)
            } else {
              // Replace the last entry with the fresher metric
              mergedHistory[mergedHistory.length - 1] = metrics
            }
          }
          if (mergedHistory.length === 0) return null
          return (
            <div className="px-5 pt-5">
              <p className="text-slate-500 text-xs font-medium mb-3 uppercase tracking-widest">History</p>
              <div className="flex justify-around items-end">
                <MetricsHistoryChart
                  label="CPU"
                  color="#10b981"
                  values={mergedHistory.map((s) => s.cpu_percent)}
                />
                <MetricsHistoryChart
                  label="Memory"
                  color="#f59e0b"
                  values={mergedHistory.map((s) => s.memory_percent)}
                />
                <MetricsHistoryChart
                  label="Disk"
                  color="#3b82f6"
                  values={mergedHistory.map((s) => s.disk_percent)}
                />
              </div>
            </div>
          )
        })()}

        {/* Heartbeat */}
        <div className="px-5 pt-4 pb-5">
          <div className="w-full bg-slate-700 rounded-lg px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-red-400 text-sm animate-pulse">♥</span>
              <span className="text-slate-400 text-xs font-medium">Heartbeat</span>
            </div>
            <span className="text-slate-200 text-xs font-mono">
              {formatHeartbeat(status?.last_heartbeat_at ?? null)}
            </span>
          </div>
        </div>

        {/* Tab Bar */}
        <TabBar />
      </div>
    </div>
  )
}
