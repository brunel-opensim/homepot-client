import { useState } from 'react'
import { useApp } from '../context/AppContext'
import { apiBaseUrl } from '../config/api'

const STEPS = ['Device Setup', 'SSO Login', 'Complete']

function StepIndicator({ current }: { current: number }) {
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

function Step1({ siteId, setSiteId, deviceName, setDeviceName, deviceType, setDeviceType, deviceOs, setDeviceOs, onNext }: {
  siteId: string
  setSiteId: (v: string) => void
  deviceName: string
  setDeviceName: (v: string) => void
  deviceType: string
  setDeviceType: (v: string) => void
  deviceOs: string
  setDeviceOs: (v: string) => void
  onNext: () => void
}) {
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
        onClick={onNext}
        disabled={!siteId.trim() || !deviceName.trim()}
        className="w-full py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors"
      >
        Next →
      </button>
    </div>
  )
}

function Step2({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleLogin() {
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`${apiBaseUrl}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || 'Login failed')
      }
      onNext()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-5 w-full">
      <div className="text-center">
        <h2 className="text-slate-200 font-semibold text-base">Sign in to your account</h2>
        <p className="text-slate-400 text-xs mt-1">Use your credentials to authorise device enrolment.</p>
      </div>

      {error && (
        <div className="p-3 bg-red-900/50 border border-red-700 rounded-lg text-sm text-red-200">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-1">
        <label className="text-slate-300 text-sm font-medium">Email</label>
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          placeholder="you@company.com"
          disabled={loading}
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-teal-500 transition-colors"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-slate-300 text-sm font-medium">Password</label>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          placeholder="Your password"
          disabled={loading}
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-teal-500 transition-colors"
        />
      </div>

      <button
        onClick={handleLogin}
        disabled={loading || !email.trim() || !password.trim()}
        className="w-full py-3 rounded-lg bg-teal-600 hover:bg-teal-500 disabled:opacity-60 text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Signing in...
          </>
        ) : (
          '🔐  Sign In'
        )}
      </button>

      <button
        onClick={onBack}
        disabled={loading}
        className="w-full py-2 rounded-lg border border-slate-600 text-slate-400 hover:text-slate-200 text-sm transition-colors"
      >
        ← Back
      </button>
    </div>
  )
}

function Step3({ siteId, deviceName, deviceType, deviceOs, onBack, onComplete }: {
  siteId: string
  deviceName: string
  deviceType: string
  deviceOs: string
  onBack: () => void
  onComplete: () => void
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleComplete() {
    setLoading(true)
    setError('')
    try {
      const reqBody = {
        site_id: siteId,
        device_name: deviceName || 'My Device',
        device_type: deviceType,
        os_details: deviceOs
      }

      const response = await fetch(`${apiBaseUrl}/devices/provision`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify(reqBody)
      })

      if (!response.ok) {
        throw new Error('Provisioning failed. Check the site ID and backend connection.')
      }

      const data = await response.json()
      const provisionedDevice = data.data
      if (!provisionedDevice?.device_id || !provisionedDevice?.api_key) {
        throw new Error('Provisioning response did not include device credentials.')
      }
      
      localStorage.setItem('homepot_token', provisionedDevice.device_id)
      localStorage.setItem('homepot_device_id', provisionedDevice.device_id)
      localStorage.setItem('homepot_site_id', siteId)
      localStorage.setItem('homepot_device_name', deviceName || 'My Device')
      localStorage.setItem('homepot_device_type', deviceType)
      localStorage.setItem('homepot_device_os', deviceOs)
      localStorage.setItem('homepot_enrollment_method', 'self-enrolled')
      sessionStorage.setItem('homepot_api_key', provisionedDevice.api_key)
      
      setLoading(false)
      onComplete()
    } catch (error) {
      console.error(error)
      setError(error instanceof Error ? error.message : 'Provisioning failed.')
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
          <span className="text-slate-200 font-medium capitalize">{deviceType.replace('_', ' ')}</span>
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
            <>
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Provisioning...
            </>
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
  const { setCurrentView, setIsProvisioned } = useApp()
  const [showClaimOption, setShowClaimOption] = useState(false)
  const [step, setStep] = useState(0)
  const [siteId, setSiteId] = useState('')
  const [deviceName, setDeviceName] = useState('')
  const [deviceType, setDeviceType] = useState('pos_terminal')
  
  // Auto-detect Operating System for default selection
  const detectOS = () => {
    const ua = navigator.userAgent.toLowerCase()
    if (ua.includes('android')) return 'android'
    if (ua.includes('win')) return 'windows'
    if (ua.includes('mac')) return 'mac'
    if (ua.includes('linux')) return 'linux'
    if (ua.includes('iphone') || ua.includes('ipad')) return 'ios'
    return 'web'
  }
  const [deviceOs, setDeviceOs] = useState(detectOS())

  function handleComplete() {
    setIsProvisioned(true)
    setCurrentView('home')
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 p-6 flex flex-col gap-6">

        <div className="flex flex-col items-center gap-1">
          <h1 className="text-slate-200 font-bold text-lg tracking-wide">HOMEPOT Agent</h1>
          <p className="text-slate-500 text-xs">Device Setup</p>
        </div>

        <StepIndicator current={step} />

        <div className="border-t border-slate-700 pt-4">
          <div className="mb-4">
            <button
              onClick={() => setCurrentView('claim')}
              className="w-full py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
            >
              Have a claim token? Click here to claim
            </button>
            <p className="text-center text-slate-500 text-xs mt-2">or set up a new device below</p>
            <div className="mt-3 mb-2 border-t border-slate-700" />
          </div>
          {step === 0 && (
            <Step1
              siteId={siteId}
              setSiteId={setSiteId}
              deviceName={deviceName}
              setDeviceName={setDeviceName}
              deviceType={deviceType}
              setDeviceType={setDeviceType}
              deviceOs={deviceOs}
              setDeviceOs={setDeviceOs}
              onNext={() => setStep(1)}
            />
          )}
          {step === 1 && (
            <Step2
              onNext={() => setStep(2)}
              onBack={() => setStep(0)}
            />
          )}
          {step === 2 && (
            <Step3
              siteId={siteId}
              deviceName={deviceName}
              deviceType={deviceType}
              deviceOs={deviceOs}
              onBack={() => setStep(0)}
              onComplete={handleComplete}
            />
          )}
        </div>

        <p className="text-center text-slate-600 text-xs">
          Step {step + 1} of {STEPS.length}
        </p>
      </div>
    </div>
  )
}
