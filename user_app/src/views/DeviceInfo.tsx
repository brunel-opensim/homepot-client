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
  const [unpairing, setUnpairing] = useState(false)
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
    setUnpairing(true)
    const deviceId = await credentialStorage.getDeviceId()
    const apiKey = await credentialStorage.getApiKey()

    let backendSuccess = false

    if (deviceId && !deviceId.startsWith('mock-token-')) {
      try {
        const res = await fetch(`${apiBaseUrl}/device/${deviceId}`, {
          method: 'DELETE',
          headers: apiKey ? { 'X-Device-ID': deviceId, 'X-API-Key': apiKey } : {},
        })
        backendSuccess = res.ok
        if (!backendSuccess) {
          const body = await res.json().catch(() => ({}))
          console.error('Backend unpair rejected:', body.detail || res.status)
        }
      } catch (error) {
        console.error('Network error during unpair:', error)
      }
    }

    if (!backendSuccess) {
      alert('Unpair request failed on server. Token will be cleared locally for safety.')
    }

    await credentialStorage.clear()

    setIsProvisioned(false)
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
          {!showConfirm ? (
            <button
              onClick={() => setShowConfirm(true)}
              className="w-full py-2.5 rounded-lg border border-red-800 bg-red-950 hover:bg-red-900 text-red-400 hover:text-red-300 text-sm font-medium transition-colors flex items-center justify-center gap-2"
            >
              🔌  Disconnect &amp; Unpair Device
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
                  disabled={unpairing}
                  className="flex-1 py-2 rounded-lg bg-red-600 hover:bg-red-500 disabled:opacity-60 text-white text-xs font-bold transition-colors flex items-center justify-center gap-1"
                >
                  {unpairing ? (
                    <>
                      <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Unpairing...
                    </>
                  ) : (
                    'Yes, Unpair'
                  )}
                </button>
              </div>
            </div>
          )}
          <p className="text-center text-slate-600 text-xs mt-2">
            Removes token and resets app to setup wizard
          </p>
        </div>

        {/* Tab Bar */}
        <TabBar />
      </div>
    </div>
  )
}
