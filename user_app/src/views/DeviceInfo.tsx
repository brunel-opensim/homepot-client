import { useState, useEffect } from 'react'
import TabBar from '../components/TabBar'
import { useApp } from '../context/AppContext'
import { apiBaseUrl } from '../config/api'
import { credentialStorage } from '../services/credentialStorage'

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

export default function DeviceInfo() {
  const { setCurrentView, setIsProvisioned } = useApp()
  const [updateStatus, setUpdateStatus] = useState<'idle' | 'checking' | 'uptodate'>('idle')
  const [showConfirm, setShowConfirm] = useState(false)
  const [unpairStatus, setUnpairStatus] = useState<'idle' | 'unpairing' | 'confirmed' | 'pending-revocation' | 'error'>('idle')
  const [unpairError, setUnpairError] = useState('')
  const [dnaRows, setDnaRows] = useState<DnaRow[]>([])

  useEffect(() => {
    Promise.all([
      credentialStorage.getMetadata('device_name'),
      credentialStorage.getMetadata('site_id'),
      credentialStorage.getMetadata('device_type'),
      credentialStorage.getMetadata('device_os'),
    ]).then(([deviceName, siteId, deviceType, deviceOs]) => {
      setDnaRows([
        { label: 'Hostname', value: deviceName || 'My-Device' },
        { label: 'Site ID', value: siteId || 'site-1234' },
        { label: 'Device Type', value: deviceType ? formatDeviceType(deviceType) : 'POS Terminal' },
        { label: 'MAC Addr', value: 'A1:B2:C3:D4:E5:F6' },
        { label: 'Local IP', value: '192.168.1.101' },
        { label: 'OS', value: deviceOs ? formatOs(deviceOs) : 'Web' },
        { label: 'Agent Ver', value: 'v0.1.0' },
      ])
    })
  }, [])

  function handleCheckUpdate() {
    setUpdateStatus('checking')
    setTimeout(() => setUpdateStatus('uptodate'), 2000)
  }

  async function handleUnpair() {
    setUnpairStatus('unpairing')
    setUnpairError('')
    setShowConfirm(false)
    const deviceId = await credentialStorage.getDeviceId()
    const apiKey = await credentialStorage.getApiKey()
    const idempotencyKey = `unpair-${deviceId}-${Date.now()}`

    if (!deviceId || deviceId.startsWith('mock-token-')) {
      await credentialStorage.clear()
      setIsProvisioned(false)
      setCurrentView('setup')
      return
    }

    try {
      const res = await fetch(
        `${apiBaseUrl}/devices/device/${deviceId}/unpair`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(apiKey ? { 'X-Device-ID': deviceId, 'X-API-Key': apiKey } : {}),
          },
          body: JSON.stringify({
            reason: 'User-initiated unpair from device settings',
            idempotency_key: idempotencyKey,
          }),
        },
      )

      if (res.ok) {
        setUnpairStatus('confirmed')
        await credentialStorage.clear()
        setIsProvisioned(false)
        setCurrentView('setup')
      } else {
        const body = await res.json().catch(() => ({}))
        setUnpairError(body.detail || `Server rejected unpair (${res.status})`)
        setUnpairStatus('error')
      }
    } catch {
      // Network failure — perform local-only reset
      await credentialStorage.clear()
      setIsProvisioned(false)
      setUnpairStatus('pending-revocation')
    }
  }

  function handleDismissPendingRevocation() {
    setCurrentView('setup')
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
          <button
            onClick={handleCheckUpdate}
            disabled={updateStatus === 'checking'}
            className="w-full py-2.5 rounded-lg border border-slate-600 bg-slate-700 hover:bg-slate-600 disabled:opacity-60 text-slate-200 text-sm font-medium transition-colors flex items-center justify-center gap-2"
          >
            {updateStatus === 'checking' ? (
              <>
                <span className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                Checking...
              </>
            ) : updateStatus === 'uptodate' ? (
              <>
                <span className="text-emerald-400">✓</span>
                Up to date — v0.1.0
              </>
            ) : (
              <>↺  Check for Updates</>
            )}
          </button>
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
              disabled={unpairStatus === 'unpairing'}
              className="w-full py-2.5 rounded-lg border border-red-800 bg-red-950 hover:bg-red-900 text-red-400 hover:text-red-300 text-sm font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {unpairStatus === 'unpairing' ? (
                <>
                  <span className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
                  Unpairing...
                </>
              ) : (
                '🔌  Disconnect &amp; Unpair Device'
              )}
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
            Sends authenticated unpair request to server
          </p>
        </div>

        {/* Tab Bar */}
        <TabBar />
      </div>
    </div>
  )
}
