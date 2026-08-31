import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import TabBar from '../components/TabBar'
import { useApp } from '../context/AppContext'
import { credentialStorage } from '../services/credentialStorage'
import { fetchDevice, unpairDevice, ApiError } from '../services/api'
import { clearCachedTelemetry, getCachedDevice, setCachedDevice } from '../services/telemetryCache'
import type { DeviceRecord } from '../services/api'
import type { UpdateStatePayload } from '../services/credentialStorage'

function formatDeviceType(v: string) {
  return v.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatOs(v: string) {
  return v.replace(/\b\w/g, c => c.toUpperCase())
}

interface DnaRow {
  label: string
  value: string
}

const OFFLINE_CHECK_TIMEOUT_MS = 12000
const OFFLINE_CHECK_INTERVAL_MS = 1500

/** Best-effort "check with the Dashboard": poll the device record until the
 *  server reports connectivity OFFLINE. Stops early on a fetch error (the
 *  dashboard is unreachable — the later unpair response is authoritative). */
async function waitForOffline(deviceId: string, apiKey: string): Promise<boolean> {
  const deadline = Date.now() + OFFLINE_CHECK_TIMEOUT_MS
  while (Date.now() < deadline) {
    try {
      const record = await fetchDevice(deviceId, apiKey)
      if (record.connectivity_state === 'offline') return true
    } catch {
      return false
    }
    await new Promise((resolve) => setTimeout(resolve, OFFLINE_CHECK_INTERVAL_MS))
  }
  return false
}

export default function DeviceInfo() {
  const navigate = useNavigate()
  const { setIsProvisioned, setIsEmulatorRunning } = useApp()
  const [updateState, setUpdateState] = useState<UpdateStatePayload['state']>({ kind: 'idle' })
  const [appVersion, setAppVersion] = useState('0.1.0')
  const [showConfirm, setShowConfirm] = useState(false)
  const [unpairStatus, setUnpairStatus] = useState<'idle' | 'disconnecting' | 'disconnected' | 'pending-revocation' | 'error'>('idle')
  const [unpairError, setUnpairError] = useState('')
  const [dnaRows, setDnaRows] = useState<DnaRow[]>([])

  useEffect(() => {
    async function loadDna() {
      const [deviceId, apiKey, deviceName, siteId, deviceType, deviceOs] = await Promise.all([
        credentialStorage.getDeviceId(),
        credentialStorage.getApiKey(),
        credentialStorage.getMetadata('device_name'),
        credentialStorage.getMetadata('site_id'),
        credentialStorage.getMetadata('device_type'),
        credentialStorage.getMetadata('device_os'),
      ])

      const localDna = window.electronAPI ? await window.electronAPI.device.dna() : null
      const detectedVersion = window.electronAPI ? await window.electronAPI.app.getVersion() : null
      if (detectedVersion) setAppVersion(detectedVersion)

      const build = (backend: DeviceRecord | null) => {
        let hostname: string
        let mac: string
        let ip: string
        let os: string
        let version = 'v0.1.0'
        let lifecycle: string | null = null

        if (localDna) {
          hostname = localDna.hostname
          mac = backend?.mac_address || localDna.mac
          ip = backend?.local_ip || localDna.ip
          os = backend?.os_details ? formatOs(backend.os_details) : formatOs(localDna.platform)
          version = `v${detectedVersion ?? '0.1.0'}`
        } else {
          hostname = backend?.name || deviceName || 'My-Device'
          mac = backend?.mac_address || '—'
          ip = backend?.local_ip || '—'
          os = backend?.os_details ? formatOs(backend.os_details) : (deviceOs ? formatOs(deviceOs) : 'Web')
        }

        if (backend?.lifecycle_state) {
          lifecycle = backend.lifecycle_state.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
        }

        const rows: DnaRow[] = [
          { label: 'Hostname', value: hostname },
          { label: 'Site ID', value: backend?.site_id || siteId || '—' },
          { label: 'Device Type', value: backend?.device_type ? formatDeviceType(backend.device_type) : (deviceType ? formatDeviceType(deviceType) : 'POS Terminal') },
          { label: 'MAC Addr', value: mac },
          { label: 'Local IP', value: ip },
          { label: 'OS', value: os },
        ]
        if (lifecycle) {
          rows.push({ label: 'Lifecycle', value: lifecycle })
        }
        rows.push({ label: 'Agent Ver', value: version })

        setDnaRows(rows)
      }

      // Phase 1: render immediately from a cached device record (or the local
      // fallbacks) so the page never shows an empty DNA template.
      build(deviceId ? getCachedDevice(deviceId) : null)

      // Phase 2: refresh from the backend and cache the result.
      if (deviceId && apiKey) {
        try {
          const backend = await fetchDevice(deviceId, apiKey)
          setCachedDevice(deviceId, backend)
          build(backend)
        } catch {
          // keep the cached/local rows
        }
      }
    }
    loadDna()
  }, [])

  async function handleCheckUpdate() {
    if (!window.electronAPI) {
      setUpdateState({ kind: 'disabled' })
      return
    }
    setUpdateState({ kind: 'checking' })
    const result = await window.electronAPI.app.checkForUpdates()
    if (result.status === 'disabled') setUpdateState({ kind: 'disabled' })
    else if (result.status === 'error') setUpdateState({ kind: 'error', message: result.message ?? 'Update check failed' })
    // 'checking' is transitionary; authoritative outcome arrives via
    // app:update:status events from the main process.
  }

  async function handleDownloadUpdate() {
    if (!window.electronAPI) return
    const result = await window.electronAPI.app.downloadUpdate()
    if (result.status === 'downloading') setUpdateState({ kind: 'downloading', percent: 0 })
    else if (result.status === 'error') setUpdateState({ kind: 'error', message: result.message })
    else if (result.status === 'disabled') setUpdateState({ kind: 'disabled' })
  }

  function handleRestartToInstall() {
    window.electronAPI?.app.restartToInstall()
    setUpdateState({ kind: 'downloaded', version: updateState.kind === 'downloaded' ? updateState.version : 'pending' })
  }

  // Subscribe to authoritative update-status events pushed from the main
  // process (electron-updater lifecycle), and seed with the current state.
  useEffect(() => {
    let unsubscribe: (() => void) | undefined
    let cancelled = false
    async function setup() {
      if (!window.electronAPI) return
      try {
        unsubscribe = window.electronAPI.updates?.onStatus((payload) => {
          const next = (payload as UpdateStatePayload).state
          if (!cancelled) setUpdateState(next)
        })
        const seed = await window.electronAPI.app?.getUpdateState?.()
        if (seed && !cancelled) setUpdateState(seed.state)
      } catch {
        // Best-effort: without an update backend the view just shows the idle
        // "Check for Updates" state.
      }
    }
    setup()
    return () => {
      cancelled = true
      unsubscribe?.()
    }
  }, [])

  async function stopDeviceProcesses() {
    // Stop the emulator/agent child processes so telemetry stops and the
    // device stays unpaired (no orphaned process re-sends/re-provisions).
    try {
      await window.electronAPI?.emulator?.stop()
    } catch {
      /* best-effort */
    }
    try {
      await window.electronAPI?.agent?.stop()
    } catch {
      /* best-effort */
    }
  }

  async function handleUnpair() {
    setUnpairStatus('disconnecting')
    setUnpairError('')
    setShowConfirm(false)
    const deviceId = await credentialStorage.getDeviceId()
    const apiKey = await credentialStorage.getApiKey()

    // Mock/absent device: local-only reset — nothing to coordinate with the server.
    if (!deviceId || deviceId.startsWith('mock-token-')) {
      await completeLocalTeardown()
      navigate('/setup')
      return
    }

    try {
      // 1) Disconnect: stop the emulator/agent so telemetry stops. The agent
      //    posts a final OFFLINE heartbeat on graceful shutdown.
      await stopDeviceProcesses()

      // 2) Check: ask the Dashboard whether the device is now OFFLINE.
      //    Best-effort and bounded — unpair below re-confirms the server-side
      //    state authoritatively, so a timeout here still proceeds.
      await waitForOffline(deviceId, apiKey ?? '')

      // 3) Unpair: the server revokes credentials, marks the device unpaired and
      //    returns an acknowledgement describing the confirmed end state.
      const ack = await unpairDevice(deviceId, apiKey ?? '', {
        reason: 'User-initiated unpair from device settings',
        idempotencyKey: `unpair-${deviceId}`,
      })

      // 4) Acknowledge: only show "Disconnected" once the Dashboard has
      //    confirmed the lifecycle is unpaired.
      if (!ack.confirmed) {
        throw new ApiError(
          'The Dashboard could not confirm the disconnect. Please retry.',
          202,
        )
      }

      clearCachedTelemetry(deviceId)
      await completeLocalTeardown()
      setUnpairStatus('disconnected')
      window.setTimeout(() => navigate('/setup'), 1800)
    } catch (err) {
      if (err instanceof ApiError) {
        setUnpairError(err.message)
        setUnpairStatus('error')
      } else {
        // Network failure — perform local-only reset
        clearCachedTelemetry(deviceId)
        await completeLocalTeardown()
        setUnpairStatus('pending-revocation')
      }
    }
  }

  /** Local teardown shared by every completion path: stop processes, wipe the
   *  emulator stash (so the device isn't re-adopted on next launch), clear the
   *  credentials file and reset provisioning state. */
  async function completeLocalTeardown() {
    await stopDeviceProcesses()
    try {
      await window.electronAPI?.emulator?.cleanup()
    } catch {
      /* best-effort */
    }
    await credentialStorage.clear()
    setIsEmulatorRunning(false)
    setIsProvisioned(false)
  }

  function handleDismissPendingRevocation() {
    navigate('/setup')
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-slate-700">
          <div>
            <h1 className="text-slate-100 font-bold text-base tracking-wide">HOMEPOT Agent</h1>
            <p className="text-slate-500 text-xs">Device Info & Settings</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center">
            <span className="text-base">⚙</span>
          </div>
        </div>

        {/* Device DNA */}
        <div className="px-5 pt-4">
          <p className="text-slate-500 text-xs font-medium uppercase tracking-widest mb-2">Device DNA</p>
          <div className="bg-slate-700 rounded-xl overflow-hidden border border-slate-600">
            {dnaRows.map((row, index) => (
              <div
                key={row.label}
                className={`flex items-center justify-between px-4 py-2.5 ${
                  index < dnaRows.length - 1 ? 'border-b border-slate-600' : ''
                }`}
              >
                <span className="text-slate-400 text-xs w-20">{row.label}</span>
                <span className="text-slate-200 text-xs font-medium font-mono text-right flex-1">
                  {row.value}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Check for Updates */}
        <div className="px-5 pt-4">
          {updateState.kind === 'disabled' || updateState.kind === 'error' ? (
            <div className={`flex flex-col gap-2 rounded-xl p-3 ${updateState.kind === 'error' ? 'bg-red-950 border border-red-800' : 'bg-slate-800 border border-slate-600'}`}>
              <p className={`text-xs font-medium text-center ${updateState.kind === 'error' ? 'text-red-300' : 'text-slate-300'}`}>
                {updateState.kind === 'error' ? '✗  Update check failed' : 'Automatic updates are not enabled for this build'}
              </p>
              {updateState.kind === 'error' && updateState.message && (
                <p className="text-red-400 text-xs text-center break-words">{updateState.message}</p>
              )}
              <p className="text-slate-400 text-xs text-center">Current version {appVersion ? `v${appVersion}` : 'unknown'}</p>
            </div>
          ) : updateState.kind === 'checking' ? (
            <button
              onClick={handleCheckUpdate}
              disabled
              className="w-full py-2.5 rounded-lg border border-slate-600 bg-slate-700 text-slate-200 text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-60"
            >
              <span className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
              Checking for updates…
            </button>
          ) : updateState.kind === 'available' ? (
            <div className="flex flex-col gap-2 bg-teal-950 border border-teal-800 rounded-xl p-4">
              <p className="text-teal-300 text-xs font-medium text-center">
                ⬇  HOMEPOT Agent v{updateState.version} available
              </p>
              <button
                onClick={handleDownloadUpdate}
                className="w-full py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold transition-colors"
              >
                Download update
              </button>
            </div>
          ) : updateState.kind === 'downloading' ? (
            <div className="flex flex-col gap-2 bg-teal-950 border border-teal-800 rounded-xl p-4">
              <p className="text-teal-300 text-xs font-medium text-center">
                Downloading… {updateState.percent}%
              </p>
              <div className="w-full h-1.5 rounded-full bg-teal-900 overflow-hidden">
                <div className="h-full bg-teal-500 transition-all" style={{ width: `${updateState.percent}%` }} />
              </div>
            </div>
          ) : updateState.kind === 'downloaded' ? (
            <div className="flex flex-col gap-2 bg-teal-950 border border-teal-800 rounded-xl p-4">
              <p className="text-teal-300 text-xs font-medium text-center">
                ✓  Update v{updateState.version} ready to install
              </p>
              <button
                onClick={handleRestartToInstall}
                className="w-full py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold transition-colors"
              >
                Restart to install
              </button>
            </div>
          ) : updateState.kind === 'not-available' ? (
            <button
              onClick={handleCheckUpdate}
              className="w-full py-2.5 rounded-lg border border-slate-600 bg-slate-700 hover:bg-slate-600 text-emerald-300 text-sm font-medium transition-colors"
            >
              ✓  Up to date — v{appVersion}
            </button>
          ) : (
            <button
              onClick={handleCheckUpdate}
              className="w-full py-2.5 rounded-lg border border-slate-600 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm font-medium transition-colors flex items-center justify-center gap-2"
            >
              <>↺  Check for Updates</>
            </button>
          )}
        </div>

        {/* Disconnect & Unpair */}
        <div className="px-5 pt-3 pb-5">
          {unpairStatus === 'pending-revocation' ? (
            <div className="flex flex-col gap-2 bg-amber-950 border border-amber-800 rounded-xl p-4">
              <p className="text-amber-300 text-xs font-medium text-center">
                ⚠  Local reset — server revocation pending
              </p>
              <p className="text-amber-400 text-xs text-center">
                The server could not be reached. Local credentials were cleared
                but server revocation could not be confirmed.
              </p>
              <button
                onClick={handleDismissPendingRevocation}
                className="w-full py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold transition-colors"
              >
                Continue to setup
              </button>
            </div>
          ) : unpairStatus === 'disconnecting' ? (
            <div className="flex flex-col gap-2 bg-slate-800 border border-slate-600 rounded-xl p-4">
              <p className="text-slate-200 text-xs font-medium text-center flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-teal-400 border-t-transparent rounded-full animate-spin" />
                Disconnecting...
              </p>
              <p className="text-slate-400 text-xs text-center">
                Stopping telemetry and verifying with the Dashboard…
              </p>
            </div>
          ) : unpairStatus === 'disconnected' ? (
            <div className="flex flex-col gap-2 bg-emerald-950 border border-emerald-800 rounded-xl p-4">
              <p className="text-emerald-300 text-xs font-medium text-center">
                ✓  Disconnected
              </p>
              <p className="text-emerald-400 text-xs text-center">
                The Dashboard has confirmed the device is unpaired. Telemetry has
                been stopped and local credentials cleared.
              </p>
            </div>
          ) : unpairStatus === 'error' ? (
            <div className="flex flex-col gap-2 bg-red-950 border border-red-800 rounded-xl p-4">
              <p className="text-red-300 text-xs font-medium text-center">
                ✗  Unpair failed
              </p>
              <p className="text-red-400 text-xs text-center">{unpairError}</p>
              <div className="flex gap-2">
                <button
                  onClick={() => { setUnpairStatus('idle'); setUnpairError('') }}
                  className="flex-1 py-2 rounded-lg border border-slate-600 text-slate-400 text-xs font-medium hover:text-slate-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleUnpair}
                  className="flex-1 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-bold transition-colors"
                >
                  Retry
                </button>
              </div>
            </div>
          ) : !showConfirm ? (
            <button
              onClick={() => setShowConfirm(true)}
              className="w-full py-2.5 rounded-lg border border-red-800 bg-red-950 hover:bg-red-900 text-red-400 hover:text-red-300 text-sm font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
            >
              🔌  Disconnect & Unpair Device
            </button>
          ) : (
            <div className="flex flex-col gap-2 bg-red-950 border border-red-800 rounded-xl p-4">
              <p className="text-red-300 text-xs font-medium text-center">
                This will wipe your token and reset the app. Are you sure?
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowConfirm(false)}
                  className="flex-1 py-2 rounded-lg border border-slate-600 text-slate-400 text-xs font-medium hover:text-slate-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleUnpair}
                  className="flex-1 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-bold transition-colors"
                >
                  Yes, Unpair
                </button>
              </div>
            </div>
          )}
          <p className="text-center text-slate-600 text-xs mt-2">
            Verifies the disconnect with the Dashboard before clearing local
            credentials.
          </p>
        </div>

        {/* Tab Bar */}
        <TabBar />
      </div>
    </div>
  )
}
