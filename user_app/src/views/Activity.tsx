import { useState, useEffect, useRef, useCallback } from 'react'
import TabBar from '../components/TabBar'
import { credentialStorage } from '../services/credentialStorage'
import {
  fetchDeviceLogs,
  fetchAuditEvents,
  fetchDeviceJobs,
  fetchDeviceAlerts,
  fetchPushHistory,
} from '../services/api'
import type { DeviceLog, AuditEvent, DeviceJob, DeviceAlert, PushHistoryEntry } from '../services/api'

const TABS = [
  { key: 'logs', label: 'Live Logs' },
  { key: 'audit', label: 'Audit' },
  { key: 'jobs', label: 'Jobs' },
  { key: 'alerts', label: 'Alerts' },
  { key: 'push', label: 'Push' },
] as const

type TabKey = (typeof TABS)[number]['key']

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
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-slate-500',
}

const JOB_STATUS_COLORS: Record<string, string> = {
  completed: 'text-emerald-400',
  failed: 'text-red-400',
  pending: 'text-amber-400',
  sent: 'text-sky-400',
  cancelled: 'text-slate-400',
}

function severityDot(severity: string): string {
  return SEVERITY_COLORS[severity.toLowerCase()] ?? 'bg-slate-500'
}

function Row({
  title,
  subtitle,
  meta,
  dot,
  titleClass,
}: {
  title: string
  subtitle?: string | null
  meta: string
  dot?: string
  titleClass?: string
}) {
  return (
    <div className="flex items-start gap-3 py-3">
      {dot && <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${dot}`} />}
      <div className="flex-1 min-w-0">
        <p className={`text-sm text-slate-200 truncate ${titleClass ?? ''}`}>{title}</p>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{subtitle}</p>}
      </div>
      <span className="text-slate-600 text-xs font-mono flex-shrink-0 pt-0.5">{meta}</span>
    </div>
  )
}

export default function Activity() {
  const [active, setActive] = useState<TabKey>('logs')
  const [logs, setLogs] = useState<DeviceLog[]>([])
  const [audit, setAudit] = useState<AuditEvent[]>([])
  const [jobs, setJobs] = useState<DeviceJob[]>([])
  const [alerts, setAlerts] = useState<DeviceAlert[]>([])
  const [push, setPush] = useState<PushHistoryEntry[]>([])
  const [error, setError] = useState('')
  const deviceIdRef = useRef<string | null>(null)
  const apiKeyRef = useRef<string | null>(null)

  useEffect(() => {
    Promise.all([credentialStorage.getDeviceId(), credentialStorage.getApiKey()]).then(
      ([did, key]) => {
        if (did) deviceIdRef.current = did
        if (key) apiKeyRef.current = key
      },
    )
  }, [])

  const refresh = useCallback(async () => {
    const dId = deviceIdRef.current
    const aKey = apiKeyRef.current
    if (!dId || !aKey) return
    try {
      const [logsRes, auditRes, jobsRes, alertsRes, pushRes] = await Promise.all([
        fetchDeviceLogs(dId, aKey),
        fetchAuditEvents(dId, aKey),
        fetchDeviceJobs(dId, aKey),
        fetchDeviceAlerts(dId, aKey),
        fetchPushHistory(dId, aKey),
      ])
      setLogs(logsRes)
      setAudit(auditRes)
      setJobs(jobsRes)
      setAlerts(alertsRes)
      setPush(pushRes)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load activity')
    }
  }, [])

  useEffect(() => {
    const credsReady = setInterval(() => {
      if (deviceIdRef.current && apiKeyRef.current) {
        clearInterval(credsReady)
        refresh()
      }
    }, 100)
    const poll = setInterval(refresh, 15000)
    return () => {
      clearInterval(credsReady)
      clearInterval(poll)
    }
  }, [refresh])

  const emptyLabel = TABS.find(t => t.key === active)?.label ?? 'items'

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-slate-700">
          <div>
            <h1 className="text-slate-100 font-bold text-base tracking-wide">HOMEPOT Agent</h1>
            <p className="text-slate-500 text-xs">Activity & History</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center">
            <span className="text-base">📊</span>
          </div>
        </div>

        {/* Tabs */}
        <div className="px-5 pt-4">
          <div className="flex gap-1 bg-slate-700 rounded-lg p-1">
            {TABS.map(tab => (
              <button
                key={tab.key}
                onClick={() => setActive(tab.key)}
                className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  active === tab.key
                    ? 'bg-emerald-500 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="px-5 pt-3">
            <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-2.5">
              <p className="text-xs text-red-300">{error}</p>
            </div>
          </div>
        )}

        {/* Content */}
        <div className="px-5 py-2 min-h-40">
          {active === 'logs' &&
            (logs.length === 0 ? (
              <EmptyState label={emptyLabel} />
            ) : (
              logs.map(log => (
                <Row
                  key={log.id}
                  title={log.error_message}
                  subtitle={log.category}
                  meta={formatTime(log.timestamp)}
                  dot={severityDot(log.severity)}
                />
              ))
            ))}
          {active === 'audit' &&
            (audit.length === 0 ? (
              <EmptyState label={emptyLabel} />
            ) : (
              audit.map(event => (
                <Row
                  key={event.id}
                  title={event.event_type}
                  subtitle={event.description}
                  meta={formatTime(event.created_at)}
                  dot="bg-sky-500"
                />
              ))
            ))}
          {active === 'jobs' &&
            (jobs.length === 0 ? (
              <EmptyState label={emptyLabel} />
            ) : (
              jobs.map(job => (
                <Row
                  key={job.job_id}
                  title={job.action}
                  subtitle={job.description}
                  meta={formatTime(job.created_at)}
                  titleClass={JOB_STATUS_COLORS[job.status] ?? undefined}
                />
              ))
            ))}
          {active === 'alerts' &&
            (alerts.length === 0 ? (
              <EmptyState label={emptyLabel} />
            ) : (
              alerts.map(alert => (
                <Row
                  key={alert.id}
                  title={alert.title}
                  subtitle={alert.description}
                  meta={formatTime(alert.timestamp)}
                  dot={severityDot(alert.severity)}
                />
              ))
            ))}
          {active === 'push' &&
            (push.length === 0 ? (
              <EmptyState label={emptyLabel} />
            ) : (
              push.map(entry => (
                <Row
                  key={entry.id}
                  title={entry.parameter_name}
                  subtitle={entry.change_reason}
                  meta={formatTime(entry.timestamp)}
                  dot={entry.was_successful ? 'bg-emerald-500' : 'bg-red-500'}
                />
              ))
            ))}
        </div>

        {/* Tab Bar */}
        <TabBar />
      </div>
    </div>
  )
}

function EmptyState({ label }: { label: string }) {
  return (
    <p className="text-center text-slate-600 text-sm py-8">No {label.toLowerCase()} yet.</p>
  )
}
