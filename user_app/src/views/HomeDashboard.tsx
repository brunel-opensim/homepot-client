import { useState, useEffect, useRef } from 'react'
import TabBar from '../components/TabBar'
import GaugeRing from '../components/GaugeRing'
import { credentialStorage } from '../services/credentialStorage'
import { fetchDeviceStatus, fetchDeviceMetrics } from '../services/api'
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
        setStatus(await fetchDeviceStatus(dId, aKey))
      } catch {
        // silently degrade
      }
    }
    async function fetchMetrics() {
      const dId = deviceIdRef.current
      const aKey = apiKeyRef.current
      if (!dId || !aKey) return
      try {
        setMetrics(await fetchDeviceMetrics(dId, aKey))
      } catch {
        // silently degrade
      }
    }
    if (!deviceIdRef.current || !apiKeyRef.current) return
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
          <div className={`w-full rounded-xl p-4 flex items-center gap-3 ${
            isOnline ? 'bg-emerald-950 border border-emerald-800' : 'bg-red-950 border border-red-800'
          }`}>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 flex-shrink-0 ${
              isOnline ? 'border-emerald-400 bg-emerald-900' : 'border-red-400 bg-red-900'
            }`}>
              <span className={`text-lg font-bold ${isOnline ? 'text-emerald-400' : 'text-red-400'}`}>
                {isOnline ? '✓' : '✕'}
              </span>
            </div>
            <div>
              <p className={`font-bold text-sm ${isOnline ? 'text-emerald-400' : 'text-red-400'}`}>
                {isOnline ? 'SECURE — ONLINE' : 'OFFLINE'}
              </p>
            </div>
            <div className={`ml-auto w-2 h-2 rounded-full flex-shrink-0 ${
              isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'
            }`} />
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
