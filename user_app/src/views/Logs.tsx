import { useState, useEffect, useCallback } from 'react'
import TabBar from '../components/TabBar'
import { credentialStorage } from '../services/credentialStorage'
import {
  fetchDeviceLogs,
  fetchDeviceAuditEvents,
  fetchDeviceCommandHistory,
  fetchDeviceAlerts,
} from '../services/api'
import type {
  DeviceLog,
  AuditEvent,
  CommandHistoryEntry,
  AlertEvent,
} from '../services/api'
import { ApiError } from '../services/api'

type AppLogEntry = Awaited<ReturnType<NonNullable<Window['electronAPI']>['app']['getRecentLogs']>>[number]

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('en-GB', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return '—'
  }
}

const SEVERITY_COLORS: Record<string, string> = {
  info: 'bg-sky-500',
  warning: 'bg-amber-500',
  error: 'bg-red-500',
  critical: 'bg-red-600',
}

function severityDot(severity: string): string {
  return SEVERITY_COLORS[severity.toLowerCase()] ?? 'bg-slate-500'
}

function formatEventType(eventType: string): string {
  return eventType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

const COMMAND_STATUS_META: Record<string, { label: string; dot: string }> = {
  pending: { label: 'Queued', dot: 'bg-amber-400' },
  sent: { label: 'Acknowledged', dot: 'bg-blue-500' },
  completed: { label: 'Completed', dot: 'bg-emerald-500' },
  failed: { label: 'Failed', dot: 'bg-red-500' },
  expired: { label: 'Expired', dot: 'bg-slate-500' },
}

function commandStatusMeta(status: string): { label: string; dot: string } {
  const normalized = (status || '').toLowerCase()
  return (
    COMMAND_STATUS_META[normalized] ?? {
      label: status || 'Unknown',
      dot: 'bg-slate-400',
    }
  )
}

const ALERT_SEVERITY_DOT: Record<string, string> = {
  critical: 'bg-red-600',
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-sky-500',
  info: 'bg-slate-400',
}

function alertSeverityDot(severity: string): string {
  return ALERT_SEVERITY_DOT[severity.toLowerCase()] ?? 'bg-slate-400'
}

function Row({
  title,
  subtitle,
  meta,
  dot,
}: {
  title: string
  subtitle?: string | null
  meta: string
  dot?: string
}) {
  return (
    <div className="flex items-start gap-3 py-3">
      {dot && <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${dot}`} />}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-200 truncate">{title}</p>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{subtitle}</p>}
      </div>
      <span className="text-slate-600 text-xs font-mono flex-shrink-0 pt-0.5">{meta}</span>
    </div>
  )
}

export default function Logs() {
  const [logs, setLogs] = useState<AppLogEntry[]>([])
  const [deviceLogs, setDeviceLogs] = useState<DeviceLog[]>([])
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([])
  const [alerts, setAlerts] = useState<AlertEvent[]>([])
  const [commandHistory, setCommandHistory] = useState<CommandHistoryEntry[]>([])
  const [diagnosticsGated, setDiagnosticsGated] = useState(false)
  const [commandHistoryGated, setCommandHistoryGated] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    const getRecentLogs = window.electronAPI?.app.getRecentLogs
    if (!getRecentLogs) {
      setError('Application logs are available in the desktop app.')
      return
    }
    try {
      setLogs(await getRecentLogs(15))
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load logs')
    }
  }, [])

  const refreshDeviceLogs = useCallback(async () => {
    const [deviceId, apiKey] = await Promise.all([
      credentialStorage.getDeviceId(),
      credentialStorage.getApiKey(),
    ])
    if (!deviceId || !apiKey) return
    try {
      setDeviceLogs(await fetchDeviceLogs(deviceId, apiKey, 50))
      setDiagnosticsGated(false)
    } catch (err) {
      setDiagnosticsGated(err instanceof ApiError && err.status === 403)
    }
  }, [])

  const refreshAuditEvents = useCallback(async () => {
    const [deviceId, apiKey] = await Promise.all([
      credentialStorage.getDeviceId(),
      credentialStorage.getApiKey(),
    ])
    if (!deviceId || !apiKey) return
    try {
      setAuditEvents(await fetchDeviceAuditEvents(deviceId, apiKey, 50))
    } catch (err) {
      setDiagnosticsGated(err instanceof ApiError && err.status === 403)
    }
  }, [])

  const refreshAlerts = useCallback(async () => {
    const [deviceId, apiKey] = await Promise.all([
      credentialStorage.getDeviceId(),
      credentialStorage.getApiKey(),
    ])
    if (!deviceId || !apiKey) return
    try {
      setAlerts(await fetchDeviceAlerts(deviceId, apiKey, 50))
    } catch (err) {
      setDiagnosticsGated(err instanceof ApiError && err.status === 403)
    }
  }, [])

  const refreshCommandHistory = useCallback(async () => {
    const [deviceId, apiKey] = await Promise.all([
      credentialStorage.getDeviceId(),
      credentialStorage.getApiKey(),
    ])
    if (!deviceId || !apiKey) return
    try {
      setCommandHistory(await fetchDeviceCommandHistory(deviceId, apiKey, 50))
      setCommandHistoryGated(false)
    } catch (err) {
      // A 403 means Manage (root_access) has not been granted for this device.
      setCommandHistoryGated(err instanceof ApiError && err.status === 403)
    }
  }, [])

  useEffect(() => {
    const initialRefresh = setTimeout(refresh, 0)
    const poll = setInterval(refresh, 15000)
    return () => {
      clearTimeout(initialRefresh)
      clearInterval(poll)
    }
  }, [refresh])

  const devicePoller = useCallback(() => {
    refreshDeviceLogs()
    refreshAuditEvents()
    refreshAlerts()
    refreshCommandHistory()
  }, [refreshDeviceLogs, refreshAuditEvents, refreshAlerts, refreshCommandHistory])

  useEffect(() => {
    const initialRefresh = setTimeout(devicePoller, 0)
    const poll = setInterval(devicePoller, 15000)
    return () => {
      clearTimeout(initialRefresh)
      clearInterval(poll)
    }
  }, [devicePoller])

  return (
    <div className="h-screen bg-slate-900 flex items-center justify-center p-4 font-sans overflow-hidden">
      <div className="w-full max-w-sm h-full bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 flex flex-col overflow-hidden">
        {/* Header — stays fixed */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-slate-700 shrink-0">
          <div>
            <h1 className="text-slate-100 font-bold text-base tracking-wide">HOMEPOT Agent</h1>
            <p className="text-slate-500 text-xs">Application Logs</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center">
            <span className="text-base">📋</span>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="px-5 pt-3 shrink-0">
            <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-2.5">
              <p className="text-xs text-red-300">{error}</p>
            </div>
          </div>
        )}

        {/* Content — scrollable logs, header + tab bar stay fixed */}
        <div className="px-5 py-2 flex-1 overflow-y-auto min-h-0 logs-scroll">
          {diagnosticsGated && (
            <p className="text-slate-500 text-xs italic pb-2 pt-2">
              Device diagnostics are hidden — grant Monitor access to this device to view
              alerts, logs, and audit activity.
            </p>
          )}
          {alerts.length > 0 && (
            <>
              <p className="text-slate-500 text-xs font-medium mb-1 uppercase tracking-widest pt-2">
                Alerts
              </p>
              {alerts.map(alert => (
                <Row
                  key={`alert-${alert.id}`}
                  title={alert.title}
                  subtitle={`${alert.category} · ${alert.status}${alert.description ? ` — ${alert.description}` : ''}`}
                  meta={formatTime(alert.timestamp)}
                  dot={alertSeverityDot(alert.severity)}
                />
              ))}
              <div className="border-t border-slate-700 my-2" />
            </>
          )}
          {commandHistoryGated && (
            <p className="text-slate-500 text-xs italic pb-2 pt-2">
              Command history is hidden — grant Manage access to this device to view it.
            </p>
          )}
          {commandHistory.length > 0 && (
            <>
              <p className="text-slate-500 text-xs font-medium mb-1 uppercase tracking-widest pt-2">
                Command History
              </p>
              {commandHistory.map(entry => {
                const statusMeta = commandStatusMeta(entry.status)
                return (
                  <Row
                    key={`command-${entry.command_id}`}
                    title={formatEventType(entry.command_type)}
                    subtitle={
                      entry.payload
                        ? `${Object.keys(entry.payload).length} parameters · ${statusMeta.label}`
                        : statusMeta.label
                    }
                    meta={formatTime(entry.created_at)}
                    dot={statusMeta.dot}
                  />
                )
              })}
              <div className="border-t border-slate-700 my-2" />
            </>
          )}
          {commandHistoryGated && commandHistory.length === 0 && (
            <>
              <p className="text-slate-500 text-xs font-medium mb-1 uppercase tracking-widest pt-2">
                Command History
              </p>
              <Row
                title="Manage access not granted"
                subtitle="Grant the Manage (root access) permission to view command history."
                meta=""
                dot="bg-slate-500"
              />
              <div className="border-t border-slate-700 my-2" />
            </>
          )}
          {auditEvents.length > 0 && (
            <>
              <p className="text-slate-500 text-xs font-medium mb-1 uppercase tracking-widest pt-2">
                Audit Trail
              </p>
              {auditEvents.map(event => (
                <Row
                  key={`audit-${event.id}`}
                  title={formatEventType(event.event_type)}
                  subtitle={event.description}
                  meta={formatTime(event.created_at)}
                  dot="bg-violet-500"
                />
              ))}
              <div className="border-t border-slate-700 my-2" />
            </>
          )}
          {deviceLogs.length > 0 && (
            <>
              <p className="text-slate-500 text-xs font-medium mb-1 uppercase tracking-widest pt-2">
                Device Logs
              </p>
              {deviceLogs.map(log => (
                <Row
                  key={`device-${log.id}`}
                  title={log.error_message}
                  subtitle={`${log.category} · code ${log.error_code ?? '—'}${log.resolved ? ' · resolved' : ''}`}
                  meta={formatTime(log.timestamp)}
                  dot={severityDot(log.severity)}
                />
              ))}
              <div className="border-t border-slate-700 my-2" />
            </>
          )}
          <p className="text-slate-500 text-xs font-medium mb-1 uppercase tracking-widest">
            Application Events
          </p>
          {logs.length === 0 ? (
            <p className="text-center text-slate-600 text-sm py-8">No application events yet.</p>
          ) : (
            logs.map(log => (
              <Row
                key={log.id}
                title={log.message}
                subtitle={`${log.category} · ${log.level}`}
                meta={formatTime(log.timestamp)}
                dot={severityDot(log.level)}
              />
            ))
          )}
        </div>

        {/* Tab Bar */}
        <TabBar />
      </div>
    </div>
  )
}
