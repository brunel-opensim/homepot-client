import { useState, useEffect, useRef, useCallback } from 'react'
import { credentialStorage } from '../services/credentialStorage'
import {
  fetchPendingCommands,
  fetchPermissions,
  updatePermissions,
  updateCommandStatus,
  reportPermissionAudit,
} from '../services/api'
import type { PendingCommand } from '../services/api'
import { emitPermissionsChanged, MANAGE_KEY, MONITOR_KEYS } from '../services/permissionsEvents'

const PERMISSION_LABELS: Record<string, string> = {
  root_access: 'Manage device (root/sudo access)',
  command_execution: 'Monitor device (diagnostics)',
  process_monitoring: 'Monitor device (processes)',
  filesystem_access: 'Monitor device (files)',
  network_monitoring: 'Monitor device (network)',
}

function permissionLabel(permission: string): string {
  return PERMISSION_LABELS[permission] ?? permission
}

export default function PermissionConsentPrompt() {
  const [request, setRequest] = useState<PendingCommand | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [capabilities, setCapabilities] = useState<Record<string, boolean>>({})
  const [capabilitiesLoaded, setCapabilitiesLoaded] = useState(false)

  const deviceIdRef = useRef<string | null>(null)
  const apiKeyRef = useRef<string | null>(null)
  const requestRef = useRef<PendingCommand | null>(null)
  const handledRef = useRef<Set<string>>(new Set())

  const data = request?.payload?.data as Record<string, unknown> | undefined
  const permission = typeof data?.permission === 'string' ? data.permission : ''
  const action = typeof data?.action === 'string' ? data.action : 'grant'
  const requestedBy = typeof data?.requested_by === 'string' ? data.requested_by : 'HOMEPOT operator'
  const isRevoke = action === 'revoke'

  // A grant cannot succeed for a permission the device's OS doesn't support
  // (e.g. root_access on an Android emulator) — surface that instead of leaving
  // the request stuck pending. Only treat a permission as unsupported once the
  // capabilities are actually loaded (a transient fetch failure must not mark
  // a supported grant as unsupported).
  const unsupported =
    capabilitiesLoaded && action === 'grant' && Boolean(permission) && !capabilities[permission]

  async function loadCapabilities() {
    const dId = deviceIdRef.current
    const aKey = apiKeyRef.current
    if (!dId || !aKey) return
    try {
      const data = await fetchPermissions(dId, aKey)
      setCapabilities(data.capabilities || {})
      setCapabilitiesLoaded(true)
    } catch {
      // Best-effort; grant failures are handled gracefully regardless.
    }
  }

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
      await loadCapabilities()
      await poll()
    }

    run()
    const interval = setInterval(run, 10000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [poll])

  // Complete the pending request as failed so it leaves the pending queue
  // instead of hanging forever.
  async function completeRequestFailed(cmd: PendingCommand, message: string) {
    const dId = deviceIdRef.current
    const aKey = apiKeyRef.current
    if (!dId || !aKey) return
    try {
      await updateCommandStatus(dId, aKey, cmd.command_id, 'failed', {
        permission,
        action,
        granted: false,
        message,
      })
    } catch {
      // Best-effort; the local prompt is still dismissed below.
    }
    handledRef.current.add(cmd.command_id)
    setRequest(null)
    requestRef.current = null
    emitPermissionsChanged()
  }

  async function dismissUnsupported() {
    if (!request) return
    setBusy(true)
    await completeRequestFailed(
      request,
      `Permission '${permission}' is not supported on this device's OS`,
    )
    setBusy(false)
  }

  async function respond(decision: 'accept' | 'deny') {
    const cmd = request
    const dId = deviceIdRef.current
    const aKey = apiKeyRef.current
    if (!cmd || !dId || !aKey) return

    setBusy(true)
    setError('')
    try {
      const granted = decision === 'accept' ? !isRevoke : isRevoke
      // The owner-facing decision is per tier, so resolving a request updates
      // the whole (supported) group — accepting "Monitor device" turns on every
      // monitor key, keeping the Permissions page toggles consistent.
      const groupKeys = permission === MANAGE_KEY ? [MANAGE_KEY] : MONITOR_KEYS
      const patch: Record<string, boolean> = {}
      for (const key of groupKeys) {
        if (capabilities[key]) patch[key] = granted
      }
      if (Object.keys(patch).length === 0) patch[permission] = granted
      await updatePermissions(dId, aKey, patch)
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
      setBusy(false)
      emitPermissionsChanged()
    } catch (err) {
      // The grant/deny failed (e.g. the OS doesn't support the permission) —
      // resolve the request so it doesn't stay pending forever.
      const message =
        err instanceof Error ? err.message : 'Failed to respond to permission request'
      await completeRequestFailed(cmd, message)
      setError(message)
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

        {unsupported ? (
          <>
            <div className="mt-3 bg-amber-950 border border-amber-800 rounded-lg px-3 py-2">
              <p className="text-xs text-amber-300">
                This permission is not supported on this device&apos;s OS, so it cannot be
                granted.
              </p>
            </div>
            <div className="flex justify-end mt-5">
              <button
                onClick={dismissUnsupported}
                disabled={busy}
                className="px-5 py-2.5 rounded-lg border border-slate-600 text-slate-300 text-sm font-medium disabled:opacity-50"
              >
                Close
              </button>
            </div>
          </>
        ) : (
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
        )}
      </div>
    </div>
  )
}
