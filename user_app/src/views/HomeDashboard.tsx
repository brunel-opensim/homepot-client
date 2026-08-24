import { useState, useEffect, useRef } from 'react'
import TabBar from '../components/TabBar'
import GaugeRing from '../components/GaugeRing'
import { credentialStorage } from '../services/credentialStorage'
import { fetchDeviceStatus, fetchDeviceMetrics } from '../services/api'
import { getCachedTelemetry, setCachedTelemetry } from '../services/telemetryCache'
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

// Lightweight "connecting" indicator: three dots that fill in sequence
// (•  ••  •••  then restart) until the connection is established.
function ConnectingDots() {
  const [dots, setDots] = useState(0)
  useEffect(() => {
    const interval = setInterval(() => setDots((d) => (d + 1) % 4), 350)
    return () => clearInterval(interval)
  }, [])
  return (
    <span className="inline-flex items-center gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={`h-1.5 w-1.5 rounded-full transition-opacity duration-300 ${
            i < dots ? 'bg-amber-400 opacity-100' : 'bg-amber-400/30 opacity-40'
          }`}
        />
      ))}
    </span>
  )
}

export default function HomeDashboard() {
  const [deviceName, setDeviceName] = useState('My Device')
  const [deviceId, setDeviceId] = useState<string | null>(null)
  const [status, setStatus] = useState<DeviceStatus | null>(null)
  const [metrics, setMetrics] = useState<DeviceMetrics | null>(null)
  const deviceIdRef = useRef<string | null>(null)
  const apiKeyRef = useRef<string | null>(null)

  useEffect(() => {
    Promise.all([
      credentialStorage.getDeviceId(),
      credentialStorage.getApiKey(),
      credentialStorage.getMetadata('device_name'),
    ]).then(([did, key, name]) => {
      if (did) { setDeviceId(did); deviceIdRef.current = did }
      if (key) apiKeyRef.current = key
      if (name) setDeviceName(name)
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
    if (!deviceIdRef.current || !apiKeyRef.current) return

    // Render any cached telemetry immediately, then refresh from the backend.
    const dId = deviceIdRef.current
    const cached = getCachedTelemetry(dId)
    if (cached) {
      if (cached.status) setStatus(cached.status)
      if (cached.metrics) setMetrics(cached.metrics)
    }

    fetchStatus()
    fetchMetrics()
    const statusInterval = setInterval(fetchStatus, 30000)
    const metricsInterval = setInterval(fetchMetrics, 15000)
    return () => {
      clearInterval(statusInterval)
      clearInterval(metricsInterval)
    }
  }, [deviceId])

  const connectivity = status?.connectivity_state || 'unknown'
  const lifecycle = status?.lifecycle_state || 'unknown'
  const isOnline = connectivity === 'online'
  const isOffline = connectivity === 'offline'
  // 'unknown' (no heartbeat yet — e.g. right after provisioning) renders as
  // CONNECTING instead of alarming red OFFLINE.
  const isConnecting = !isOnline && !isOffline

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
              👤
            </div>
          </div>
        </div>

        {/* Status Badge */}
        <div className="px-5 pt-4">
          <div className={`w-full rounded-xl p-4 flex items-center gap-3 ${statusStyles.card}`}>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 flex-shrink-0 ${statusStyles.circle}`}>
              <span className={`text-lg font-bold flex items-center ${statusStyles.text}`}>
                {isConnecting ? <ConnectingDots /> : statusStyles.glyph}
              </span>
            </div>
            <div>
              <p className={`font-bold text-sm ${statusStyles.text}`}>
                {statusStyles.label}
              </p>
            </div>
            <div className={`ml-auto w-2 h-2 rounded-full flex-shrink-0 ${statusStyles.dot}`} />
          </div>
        </div>

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
