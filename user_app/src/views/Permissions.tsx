import { useState, useEffect, useRef, useCallback } from 'react'
import TabBar from '../components/TabBar'
import { credentialStorage } from '../services/credentialStorage'
import { fetchPermissions as fetchPermissionsApi, updatePermissions } from '../services/api'

interface PermissionEntry {
  key: string
  label: string
  description: string
  enabled: boolean
  supported: boolean
}

const PERMISSION_DEFS: { key: string; label: string; description: string }[] = [
  { key: 'root_access', label: 'Root / Full Access', description: 'Allows full system scan' },
  { key: 'process_monitoring', label: 'Process Monitoring', description: 'View running processes' },
  { key: 'filesystem_access', label: 'File System Access', description: 'Scan files & folders' },
  { key: 'network_monitoring', label: 'Network Monitoring', description: 'Track network connections' },
]

function Toggle({ enabled, disabled, saving, onChange }: { enabled: boolean; disabled: boolean; saving: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      disabled={disabled || saving}
      className={`relative w-12 h-6 rounded-full p-1 transition-colors duration-200 flex-shrink-0 focus:outline-none ${
        saving ? 'bg-slate-600 cursor-wait' : enabled ? 'bg-emerald-500' : 'bg-slate-600'
      } ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
    >
      {saving ? (
        <span className="block w-4 h-4 mx-auto border-2 border-slate-300 border-t-transparent rounded-full animate-spin" />
      ) : (
        <span className={`block w-4 h-4 bg-white rounded-full shadow-md transition-transform duration-200 ${
          enabled ? 'translate-x-6' : 'translate-x-0'
        }`} />
      )}
    </button>
  )
}

export default function Permissions() {
  const [permissions, setPermissions] = useState<PermissionEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [savingKeys, setSavingKeys] = useState<Set<string>>(new Set())
  const [overrideNotice, setOverrideNotice] = useState(false)

  const deviceIdRef = useRef<string | null>(null)
  const apiKeyRef = useRef<string | null>(null)
  const debounceRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())
  const latestPermissionsRef = useRef<PermissionEntry[]>([])

  useEffect(() => {
    Promise.all([
      credentialStorage.getDeviceId(),
      credentialStorage.getApiKey(),
    ]).then(([did, key]) => {
      if (did) deviceIdRef.current = did
      if (key) apiKeyRef.current = key
    })
  }, [])

  const fetchPermissions = useCallback(async (silent = false) => {
    const dId = deviceIdRef.current
    const aKey = apiKeyRef.current
    if (!dId || !aKey) return

    if (!silent) {
      setLoading(true)
      setError('')
    }
    try {
      const data = await fetchPermissionsApi(dId, aKey)
      const perms: Record<string, boolean> = data.permissions || {}
      const caps: Record<string, boolean> = data.capabilities || {}

      const entries: PermissionEntry[] = PERMISSION_DEFS.map(def => ({
        ...def,
        enabled: perms[def.key] ?? false,
        supported: caps[def.key] ?? false,
      }))

      if (silent) {
        const current = latestPermissionsRef.current
        const changedExternally =
          current.length > 0 &&
          entries.some((entry, index) => {
            const prev = current[index]
            return prev && prev.enabled !== entry.enabled
          })
        if (changedExternally) setOverrideNotice(true)
      }

      setPermissions(entries)
      latestPermissionsRef.current = entries
    } catch (err) {
      if (!silent) {
        setError(err instanceof Error ? err.message : 'Failed to load permissions')
      }
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const credsReady = setInterval(() => {
      if (deviceIdRef.current && apiKeyRef.current) {
        clearInterval(credsReady)
        fetchPermissions()
      }
    }, 100)
    const refresh = setInterval(() => {
      fetchPermissions(true)
    }, 15000)
    return () => {
      clearInterval(credsReady)
      clearInterval(refresh)
    }
  }, [fetchPermissions])

  const syncPermission = useCallback(async (key: string, enabled: boolean) => {
    const dId = deviceIdRef.current
    const aKey = apiKeyRef.current
    if (!dId || !aKey) return

    setSavingKeys(prev => new Set(prev).add(key))
    try {
      await updatePermissions(dId, aKey, { [key]: enabled })
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Sync failed'
      setError(msg)
      const reverted = latestPermissionsRef.current.map(p =>
        p.key === key ? { ...p, enabled: !enabled } : p,
      )
      setPermissions(reverted)
      latestPermissionsRef.current = reverted
    } finally {
      setSavingKeys(prev => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
    }
  }, [])

  function handleToggle(key: string) {
    setOverrideNotice(false)
    setPermissions(prev => {
      const next = prev.map(p => (p.key === key ? { ...p, enabled: !p.enabled } : p))
      latestPermissionsRef.current = next
      return next
    })

    const existing = debounceRef.current.get(key)
    if (existing) clearTimeout(existing)

    const timeout = setTimeout(() => {
      const entry = latestPermissionsRef.current.find(p => p.key === key)
      if (entry) syncPermission(key, entry.enabled)
      debounceRef.current.delete(key)
    }, 300)

    debounceRef.current.set(key, timeout)
  }

  useEffect(() => {
    return () => {
      debounceRef.current.forEach(t => clearTimeout(t))
      debounceRef.current.clear()
    }
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
        <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 p-8 flex flex-col items-center gap-4">
          <span className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-400 text-sm">Loading permissions…</p>
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
            <p className="text-slate-500 text-xs">Permissions & Access Control</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center">
            <span className="text-base">🔒</span>
          </div>
        </div>

        {/* Description */}
        <div className="px-5 pt-4">
          <p className="text-slate-400 text-sm">
            Control what the Admin Dashboard can access on this device.
          </p>
        </div>

        {/* Operator/admin override notice */}
        {overrideNotice && (
          <div className="px-5 pt-3">
            <div className="bg-amber-950 border border-amber-800 rounded-lg px-4 py-2.5 flex items-start gap-2">
              <span className="text-amber-400 text-sm shrink-0">⚠</span>
              <p className="text-xs text-amber-300">
                An operator or administrator has updated this device's permissions. Review
                and adjust if needed.
              </p>
            </div>
          </div>
        )}

        {/* Error banner */}
        {error && (
          <div className="px-5 pt-3">
            <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-2.5 flex items-center gap-2">
              <span className="text-red-400 text-sm shrink-0">⚠</span>
              <p className="text-xs text-red-300">{error}</p>
            </div>
          </div>
        )}

        {/* Permission Toggles */}
        <div className="px-5 pt-4 flex flex-col gap-0">
          {permissions.map((perm, index) => (
            <div key={perm.key}>
              <div className="flex items-center justify-between py-3.5">
                <div className="flex flex-col gap-0.5 flex-1 mr-4">
                  <span className={`text-sm font-medium ${perm.supported ? 'text-slate-200' : 'text-slate-500'}`}>
                    {perm.label}
                  </span>
                  <span className="text-slate-500 text-xs">
                    {perm.supported ? perm.description : 'Not supported on this OS'}
                  </span>
                </div>
                <Toggle
                  enabled={perm.enabled}
                  disabled={!perm.supported}
                  saving={savingKeys.has(perm.key)}
                  onChange={() => handleToggle(perm.key)}
                />
              </div>
              {index < permissions.length - 1 && (
                <div className="border-t border-slate-700" />
              )}
            </div>
          ))}
        </div>

        {/* Sync status */}
        <div className="px-5 pt-3 pb-5">
          <div className={`w-full rounded-lg px-4 py-2.5 flex items-center gap-2 transition-all duration-300 ${
            savingKeys.size > 0
              ? 'bg-amber-950 border border-amber-800'
              : 'bg-slate-700 border border-slate-600'
          }`}>
            <span className={`text-sm ${savingKeys.size > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
              {savingKeys.size > 0 ? '⏳' : '✓'}
            </span>
            <p className="text-xs text-slate-300">
              {savingKeys.size > 0
                ? `Syncing ${savingKeys.size} change${savingKeys.size > 1 ? 's' : ''}…`
                : 'All changes synced to the server.'}
            </p>
          </div>
        </div>

        {/* Tab Bar */}
        <TabBar />
      </div>
    </div>
  )
}