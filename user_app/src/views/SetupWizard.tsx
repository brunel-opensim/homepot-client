import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { apiBaseUrl } from '../config/api'
import { credentialStorage } from '../services/credentialStorage'

function formatDeviceType(v: string) {
  return v.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function StepIndicator({ current }: { current: number }) {
  const STEPS = ['Device Setup', 'SSO Login', 'Complete']
  return (
    <div className="flex items-center justify-center gap-2 w-full">
      {STEPS.map((label, i) => (
        <div key={label} className="flex items-center gap-2">
          <div className="flex flex-col items-center gap-1">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors ${
              i < current
                ? 'bg-emerald-500 border-emerald-500 text-white'
                : i === current
                ? 'border-emerald-500 text-emerald-400 bg-slate-900'
                : 'border-slate-600 text-slate-500 bg-slate-900'
            }`}>
              {i < current ? '✓' : i + 1}
            </div>
            <span className={`text-xs ${i === current ? 'text-emerald-400' : 'text-slate-500'}`}>
              {label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div className={`w-10 h-0.5 mb-4 ${i < current ? 'bg-emerald-500' : 'bg-slate-700'}`} />
          )}
        </div>
      ))}
    </div>
  )
}

function Step1() {
  const navigate = useNavigate()
  const { setupState, setSetupState } = useApp()
  const [siteId, setSiteId] = useState(setupState.siteId)
  const [deviceName, setDeviceName] = useState(setupState.deviceName)
  const [deviceType, setDeviceType] = useState(setupState.deviceType)
  const [deviceOs, setDeviceOs] = useState(setupState.deviceOs)

  const handleNext = () => {
    setSetupState({ siteId, deviceName, deviceType, deviceOs })
    navigate('/signin')
  }

  return (
    <div className="flex flex-col gap-5 w-full">
      <div className="text-center">
        <h2 className="text-slate-200 font-semibold text-base">Welcome! Let's set up your device.</h2>
        <p className="text-slate-400 text-xs mt-1">This only takes a minute.</p>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-slate-300 text-sm font-medium">
          Site ID <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          value={siteId}
          onChange={e => setSiteId(e.target.value)}
          placeholder="Enter your Site ID"
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
        />
        <p className="text-slate-500 text-xs">Provided by your IT administrator.</p>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-slate-300 text-sm font-medium">
          Hostname <span className="text-emerald-500 font-normal">*</span>
        </label>
        <input
          type="text"
          value={deviceName}
          onChange={e => setDeviceName(e.target.value)}
          placeholder="e.g. Kasi-Laptop"
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-slate-300 text-sm font-medium">
          Device Type <span className="text-red-400">*</span>
        </label>
        <select
          value={deviceType}
          onChange={e => setDeviceType(e.target.value)}
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
        >
          <option value="pos_terminal">POS Terminal</option>
          <option value="virtual_terminal">Virtual Terminal</option>
          <option value="kiosk">Kiosk</option>
          <option value="tablet">Tablet</option>
          <option value="mobile_scanner">Mobile Scanner</option>
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-slate-300 text-sm font-medium">
          Operating System <span className="text-red-400">*</span>
        </label>
        <select
          value={deviceOs}
          onChange={e => setDeviceOs(e.target.value)}
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
        >
          <option value="windows">Windows</option>
          <option value="linux">Linux</option>
          <option value="mac">macOS</option>
          <option value="android">Android</option>
          <option value="ios">iOS</option>
          <option value="web">Web Browser</option>
        </select>
      </div>

      <button
        onClick={handleNext}
        disabled={!siteId.trim() || !deviceName.trim()}
        className="w-full py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors"
      >
        Next →
      </button>
    </div>
  )
}

function ReviewStep({ onBack }: { onBack: () => void }) {
  const navigate = useNavigate()
  const { setupState, setIsProvisioned } = useApp()
  const { siteId, deviceName, deviceType, deviceOs } = setupState
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const isDev = import.meta.env.DEV

  async function handleComplete() {
    setLoading(true)
    setError('')
    try {
      if (isDev) {
        await credentialStorage.save({
          deviceId: `dev-device-${Date.now()}`,
          apiKey: `dev-api-key-${crypto.randomUUID()}`,
          siteId: siteId || 'dev-site',
          deviceName: deviceName || 'Dev Device',
          deviceType,
          deviceOs,
          enrollmentMethod: 'self-enrolled',
        })
        setLoading(false)
        setIsProvisioned(true)
        navigate('/home')
        return
      }

      const reqBody = { site_id: siteId, device_name: deviceName || 'My Device', device_type: deviceType, os_details: deviceOs }
      const response = await fetch(`${apiBaseUrl}/devices/provision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(reqBody),
      })

      if (!response.ok) throw new Error('Provisioning failed. Check the site ID and backend connection.')

      const data = await response.json()
      const d = data.data
      if (!d?.device_id || !d?.api_key) throw new Error('Provisioning response did not include device credentials.')

      await credentialStorage.save({ deviceId: d.device_id, apiKey: d.api_key, siteId, deviceName: deviceName || 'My Device', deviceType, deviceOs, enrollmentMethod: 'self-enrolled' })
      setLoading(false)
      setIsProvisioned(true)
      navigate('/home')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provisioning failed.')
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-5 w-full items-center text-center">
      <div className="w-16 h-16 rounded-full bg-emerald-900 border-2 border-emerald-500 flex items-center justify-center">
        <span className="text-3xl">✓</span>
      </div>

      <div>
        <h2 className="text-slate-200 font-semibold text-base">Review Settings</h2>
        <p className="text-slate-400 text-xs mt-1">Please confirm your device details before provisioning.</p>
      </div>

      <div className="w-full bg-slate-700 rounded-lg p-3 text-left text-sm space-y-1">
        <div className="flex justify-between">
          <span className="text-slate-400">Site ID</span>
          <span className="text-slate-200 font-medium">{siteId}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Hostname</span>
          <span className="text-slate-200 font-medium">{deviceName || '—'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Device Type</span>
          <span className="text-slate-200 font-medium capitalize">{formatDeviceType(deviceType)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Operating System</span>
          <span className="text-slate-200 font-medium capitalize">{deviceOs}</span>
        </div>
      </div>

      <div className="w-full flex gap-3 mt-2">
        <button
          onClick={onBack}
          disabled={loading}
          className="flex-1 py-3 rounded-lg border border-slate-600 text-slate-300 hover:text-white hover:bg-slate-700 disabled:opacity-60 font-semibold text-sm transition-colors"
        >
          Edit
        </button>
        <button
          onClick={handleComplete}
          disabled={loading}
          className="flex-[2] py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Provisioning...</>
          ) : (
            'Complete Setup'
          )}
        </button>
      </div>
      {error && <p className="w-full text-left text-xs text-red-400">{error}</p>}
    </div>
  )
}

export default function SetupWizard() {
  const navigate = useNavigate()
  const location = useLocation()
  const isReview = location.pathname === '/setup/review'

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 p-6 flex flex-col gap-6">

        <div className="flex flex-col items-center gap-1">
          <h1 className="text-slate-200 font-bold text-lg tracking-wide">HOMEPOT Agent</h1>
          <p className="text-slate-500 text-xs">Device Setup</p>
        </div>

        <StepIndicator current={isReview ? 2 : 0} />

        <div className="border-t border-slate-700 pt-4">
          {!isReview && (
            <div className="mb-4">
              <button
                onClick={() => navigate('/claim')}
                className="w-full py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
              >
                Have a claim token? Click here to claim
              </button>
              <p className="text-center text-slate-500 text-xs mt-2">or set up a new device below</p>
              <div className="mt-3 mb-2 border-t border-slate-700" />
            </div>
          )}

          {isReview ? (
            <ReviewStep onBack={() => navigate('/setup')} />
          ) : (
            <Step1 />
          )}
        </div>

        <p className="text-center text-slate-600 text-xs">
          Step {isReview ? 3 : 1} of 3
        </p>
      </div>
    </div>
  )
}
