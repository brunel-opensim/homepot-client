import { useState, useEffect, useRef, useCallback } from 'react'
import { credentialStorage } from '../services/credentialStorage'
import {
  fetchPendingCommands,
  ackCommand,
  updatePermissions,
  updateCommandStatus,
  reportPermissionAudit,
} from '../services/api'
import type { PendingCommand } from '../services/api'

const PERMISSION_LABELS: Record<string, string> = {
  root_access: 'Root / Full Access',
  process_monitoring: 'Process Monitoring',
  filesystem_access: 'File System Access',
  network_monitoring: 'Network Monitoring',
}

function permissionLabel(permission: string): string {
  return PERMISSION_LABELS[permission] ?? permission
}

export default function PermissionConsentPrompt() {
  const [request, setRequest] = useState<PendingCommand | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const deviceIdRef = useRef<string | null>(null)
  const apiKeyRef = useRef<string | null>(null)
  const requestRef = useRef<PendingCommand | null>(null)
  const handledRef = useRef<Set<string>>(new Set())

  const data = request?.payload?.data as Record<string, unknown> | undefined
  const permission = typeof data?.permission === 'string' ? data.permission : ''
  const action = typeof data?.action === 'string' ? data.action : 'grant'
  const requestedBy = typeof data?.requested_by === 'string' ? data.requested_by : 'HOMEPOT operator'
  const isRevoke = action === 'revoke'

  const poll = useCallback(async () => {
    const dId = deviceIdRef.current
    const aKey = apiKeyRef.current
    if (!dId || !aKey || requestRef.current) return
    try {
      const commands = await fetchPendingCommands(dId, aKey)
      if (requestRef.current) return
      const cmd = commands.find(
        c => c.command_type === 'request_permission' && !handledRef.current.has(c.command_id),
      )
      if (!cmd) return
      await ackCommand(dId, aKey, cmd.command_id)
      if (requestRef.current) return
      setRequest(cmd)
      requestRef.current = cmd
    } catch {
      // silently degrade until next poll
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function ensureCreds(): Promise<boolean> {
      const [did, key] = await Promise.all([
        credentialStorage.getDeviceId(),
        credentialStorage.getApiKey(),
      ])
      if (did) deviceIdRef.current = did
      if (key) apiKeyRef.current = key
      return Boolean(deviceIdRef.current && apiKeyRef.current)
    }

    async function run() {
      if (cancelled) return
      if (!deviceIdRef.current || !apiKeyRef.current) {
        if (!(await ensureCreds()) || cancelled) return
      }
      await poll()
    }

    run()
    const interval = setInterval(run, 10000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [poll])

  async function respond(decision: 'accept' | 'deny') {
    const cmd = request
    const dId = deviceIdRef.current
    const aKey = apiKeyRef.current
    if (!cmd || !dId || !aKey) return

    setBusy(true)
    setError('')
    try {
      const granted = decision === 'accept' ? !isRevoke : isRevoke
      await updatePermissions(dId, aKey, { [permission]: granted })
      await reportPermissionAudit(dId, aKey, { permission, granted, requestedBy, action })
      await updateCommandStatus(dId, aKey, cmd.command_id, 'completed', {
        permission,
        action,
        granted,
        message: granted
          ? `Permission '${permission}' granted by device owner`
          : `Permission '${permission}' denied by device owner`,
      })
      handledRef.current.add(cmd.command_id)
      setRequest(null)
      requestRef.current = null
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to respond to permission request')
      setBusy(false)
    }
  }

  if (!request) return null

  const title = isRevoke ? 'Revoke access requested' : 'Permission request'
  const body = isRevoke
    ? `${requestedBy} is requesting to revoke "${permissionLabel(permission)}".`
    : `${requestedBy} is requesting access to "${permissionLabel(permission)}".`
  const acceptLabel = isRevoke ? 'Approve revocation' : 'Allow'

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-600 p-6">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xl">🔐</span>
          <h2 className="text-slate-100 font-bold text-base">{title}</h2>
        </div>
        <p className="text-slate-300 text-sm leading-relaxed">{body}</p>
        <p className="text-slate-500 text-xs mt-2">
          You can review and adjust permissions any time under Permissions.
        </p>

        {error && (
          <div className="mt-3 bg-red-950 border border-red-800 rounded-lg px-3 py-2">
            <p className="text-xs text-red-300">{error}</p>
          </div>
        )}

        <div className="flex gap-3 mt-5">
          <button
            onClick={() => respond('deny')}
            disabled={busy}
            className="flex-1 py-2.5 rounded-lg border border-slate-600 text-slate-300 text-sm font-medium disabled:opacity-50"
          >
            Deny
          </button>
          <button
            onClick={() => respond('accept')}
            disabled={busy}
            className={`flex-1 py-2.5 rounded-lg text-sm font-medium disabled:opacity-50 ${
              isRevoke ? 'bg-orange-500 text-white' : 'bg-emerald-500 text-white'
            }`}
          >
            {busy ? '…' : acceptLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
