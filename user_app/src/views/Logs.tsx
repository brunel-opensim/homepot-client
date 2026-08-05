import { useState, useEffect, useCallback } from 'react'
import TabBar from '../components/TabBar'

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
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-slate-500',
}

function severityDot(severity: string): string {
  return SEVERITY_COLORS[severity.toLowerCase()] ?? 'bg-slate-500'
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

  useEffect(() => {
    const initialRefresh = setTimeout(refresh, 0)
    const poll = setInterval(refresh, 15000)
    return () => {
      clearTimeout(initialRefresh)
      clearInterval(poll)
    }
  }, [refresh])

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-slate-700">
          <div>
            <h1 className="text-slate-100 font-bold text-base tracking-wide">HOMEPOT Agent</h1>
            <p className="text-slate-500 text-xs">Application Logs</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center">
            <span className="text-base">📊</span>
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
          {logs.length === 0 ? (
            <p className="text-center text-slate-600 text-sm py-8">No application events yet.</p>
          ) : (
            logs.map(log => (
              <Row
                key={log.id}
                title={log.message}
                subtitle={log.category}
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
