import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { apiBaseUrl } from '../config/api'
import { credentialStorage } from '../services/credentialStorage'
import { bootstrapProvision, checkDeviceName } from '../services/api'

const EMULATOR_TYPES: { value: string; label: string; os: string; description: string }[] = [
  { value: 'linux_pos', label: 'Linux POS', os: 'Linux 6.8.0 (Debian 12)', description: 'Simulates a Linux-based POS terminal' },
  { value: 'android_pos', label: 'Android POS', os: 'Android 14', description: 'Simulates an Android POS tablet' },
]

function formatDeviceType(v: string) {
  return v.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function detectOS(): string {
  const uaData = (navigator as unknown as { userAgentData?: { platform?: string } }).userAgentData
  if (uaData?.platform) {
    const p = uaData.platform.toLowerCase()
    if (p.includes('android')) return 'android'
    if (p.includes('iphone') || p.includes('ipad') || p.includes('ios')) return 'ios'
    if (p.includes('mac')) return 'mac'
    if (p.includes('win')) return 'windows'
    if (p.includes('linux')) return 'linux'
  }
  const platform = navigator.platform.toLowerCase()
  const ua = navigator.userAgent.toLowerCase()
  if (ua.includes('android')) return 'android'
  if (/iphone|ipad|ipod/.test(ua)) return 'ios'
  if (platform.includes('mac')) return 'mac'
  if (platform.includes('win')) return 'windows'
  if (platform.includes('linux') || ua.includes('cros')) return 'linux'
  return 'web'
}

function StepIndicator({ current }: { current: number }) {
  const STEPS = ['Device Setup', 'Method', 'Emulator', 'Complete']
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
  const [bootstrapKey, setBootstrapKey] = useState(setupState.bootstrapKey)
  const [nameStatus, setNameStatus] = useState<'idle' | 'checking' | 'available' | 'taken'>('idle')

  useEffect(() => {
    if (!siteId.trim() || !bootstrapKey.trim() || !deviceName.trim()) {
      return
    }
    let cancelled = false
    const timer = setTimeout(async () => {
      setNameStatus('checking')
      try {
        const res = await checkDeviceName({
          site_id: siteId.trim(),
          bootstrap_key: bootstrapKey.trim(),
          device_name: deviceName.trim(),
        })
        if (!cancelled) setNameStatus(res.available ? 'available' : 'taken')
      } catch {
        if (!cancelled) setNameStatus('idle')
      }
    }, 500)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [siteId, bootstrapKey, deviceName])

  const handleNext = () => {
    const resolvedOs = deviceOs === 'auto' ? detectOS() : deviceOs
    setSetupState({ siteId, deviceName, deviceType, deviceOs: resolvedOs, bootstrapKey })
    navigate('/method')
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
          onChange={e => {
            setSiteId(e.target.value)
            if (!e.target.value.trim()) setNameStatus('idle')
          }}
          placeholder="Enter your Site ID"
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
        />
        <p className="text-slate-500 text-xs">Provided by your IT administrator.</p>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-slate-300 text-sm font-medium">
          Bootstrap Key <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          value={bootstrapKey}
          onChange={e => {
            setBootstrapKey(e.target.value)
            if (!e.target.value.trim()) setNameStatus('idle')
          }}
          placeholder="Enter your Bootstrap Key"
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
        />
        <p className="text-slate-500 text-xs">
          Provided by your IT administrator. For emulator testing use the dev key: <span className="text-slate-400">homepot-dev-emulator-key</span>.
        </p>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-slate-300 text-sm font-medium">
          Device Name <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          value={deviceName}
          onChange={e => {
            setDeviceName(e.target.value)
            if (!e.target.value.trim()) setNameStatus('idle')
          }}
          placeholder="e.g. Device-001"
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
        />
        {nameStatus === 'checking' && (
          <p className="text-slate-500 text-xs">Checking name availability…</p>
        )}
        {nameStatus === 'available' && (
          <p className="text-emerald-500 text-xs">✓ Name available</p>
        )}
        {nameStatus === 'taken' && (
          <p className="text-red-400 text-xs">✗ Name already in use in this site — pick a different name.</p>
        )}
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
          <option value="">-</option>
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
          <option value="auto">Auto-detect</option>
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
        disabled={!siteId.trim() || !bootstrapKey.trim() || !deviceName.trim() || !deviceType || nameStatus === 'taken'}
        className="w-full py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors"
      >
        Next →
      </button>
    </div>
  )
}

function ReviewStep({ onBack }: { onBack: () => void }) {
  const navigate = useNavigate()
  const { setupState, useEmulator, emulatorType, setIsProvisioned, setIsEmulatorRunning } = useApp()
  const { siteId, deviceName, deviceType, deviceOs, bootstrapKey } = setupState
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const isDev = import.meta.env.DEV

  async function handleComplete() {
    setLoading(true)
    setError('')
    try {
      if (useEmulator && window.electronAPI?.emulator) {
        const config = {
          emulatorType,
          backendUrl: apiBaseUrl.replace('/api/v1', ''),
          siteId,
          bootstrapKey,
          deviceName: deviceName || 'Emulated Device',
          deviceType,
        }
        const result = await window.electronAPI.emulator.start(config)
        await credentialStorage.save({
          deviceId: result.deviceId,
          apiKey: result.apiKey,
          siteId,
          deviceName: deviceName || 'Emulated Device',
          deviceType,
          deviceOs,
          enrollmentMethod: 'emulated',
        })
        setLoading(false)
        setIsEmulatorRunning(true)
        setIsProvisioned(true)
        navigate('/home')
        return
      }

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

      const reqBody = {
        site_id: siteId,
        bootstrap_key: bootstrapKey,
        device_name: deviceName || 'My Device',
        device_type: deviceType,
        os_details: deviceOs,
      }
      const d = await bootstrapProvision(reqBody)
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
          <span className="text-slate-400">Device Name</span>
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

function EmulatorConfigStep() {
  const navigate = useNavigate()
  const { emulatorType, setEmulatorType, setUseEmulator, setSetupState, setupState } = useApp()
  const selected = EMULATOR_TYPES.find(t => t.value === emulatorType) ?? EMULATOR_TYPES[0]

  const handleNext = () => {
    setUseEmulator(true)
    setSetupState({ ...setupState, deviceOs: selected.os })
    navigate('/setup/review')
  }

  return (
    <div className="flex flex-col gap-5 w-full">
      <div className="text-center">
        <h2 className="text-slate-200 font-semibold text-base">Configure Emulator</h2>
        <p className="text-slate-400 text-xs mt-1">Choose the device type to simulate.</p>
      </div>

      <div className="flex flex-col gap-2">
        {EMULATOR_TYPES.map(t => (
          <button
            key={t.value}
            onClick={() => setEmulatorType(t.value)}
            className={`w-full text-left px-4 py-3 rounded-lg border-2 transition-colors ${
              emulatorType === t.value
                ? 'border-emerald-500 bg-slate-700'
                : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-slate-200 font-medium text-sm">{t.label}</span>
              {emulatorType === t.value && (
                <span className="text-emerald-400 text-sm">✓</span>
              )}
            </div>
            <p className="text-slate-400 text-xs mt-1">{t.description}</p>
            <p className="text-slate-500 text-xs">{t.os}</p>
          </button>
        ))}
      </div>

      <div className="flex gap-3 mt-2">
        <button
          onClick={() => navigate('/method')}
          className="flex-1 py-3 rounded-lg border border-slate-600 text-slate-300 hover:text-white hover:bg-slate-700 font-semibold text-sm transition-colors"
        >
          Back
        </button>
        <button
          onClick={handleNext}
          className="flex-[2] py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm transition-colors"
        >
          Next →
        </button>
      </div>
    </div>
  )
}

function ModeStep() {
  const navigate = useNavigate()
  const { useEmulator, setUseEmulator, emulatorType, setEmulatorType } = useApp()
  const [mode, setMode] = useState<'real' | 'emulator'>(useEmulator ? 'emulator' : 'real')

  const handleNext = () => {
    if (mode === 'emulator') {
      setUseEmulator(true)
      if (!EMULATOR_TYPES.find(t => t.value === emulatorType)) {
        setEmulatorType(EMULATOR_TYPES[0].value)
      }
      navigate('/emulator')
    } else {
      setUseEmulator(false)
      navigate('/signin')
    }
  }

  return (
    <div className="flex flex-col gap-5 w-full">
      <div className="text-center">
        <h2 className="text-slate-200 font-semibold text-base">Setup Method</h2>
        <p className="text-slate-400 text-xs mt-1">Choose how to set up this device.</p>
      </div>

      <div className="flex flex-col gap-3">
        <button
          onClick={() => setMode('real')}
          className={`w-full text-left px-4 py-4 rounded-lg border-2 transition-colors ${
            mode === 'real' ? 'border-emerald-500 bg-slate-700' : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-slate-200 font-medium text-sm">Set up a real device</span>
            {mode === 'real' && <span className="text-emerald-400 text-sm">✓</span>}
          </div>
          <p className="text-slate-400 text-xs mt-1">Provision a physical device using a bootstrap key.</p>
        </button>

        <button
          onClick={() => setMode('emulator')}
          className={`w-full text-left px-4 py-4 rounded-lg border-2 transition-colors ${
            mode === 'emulator' ? 'border-emerald-500 bg-slate-700' : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-slate-200 font-medium text-sm">Launch emulated device</span>
            {mode === 'emulator' && <span className="text-emerald-400 text-sm">✓</span>}
          </div>
          <p className="text-slate-400 text-xs mt-1">Start a simulated device for development and testing.</p>
        </button>
      </div>

      <div className="flex gap-3 mt-2">
        <button
          onClick={() => navigate('/setup')}
          className="flex-1 py-3 rounded-lg border border-slate-600 text-slate-300 hover:text-white hover:bg-slate-700 font-semibold text-sm transition-colors"
        >
          Back
        </button>
        <button
          onClick={handleNext}
          className="flex-[2] py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm transition-colors"
        >
          Next →
        </button>
      </div>
    </div>
  )
}

export default function SetupWizard() {
  const navigate = useNavigate()
  const location = useLocation()
  const isReview = location.pathname === '/setup/review'
  const isEmulatorConfig = location.pathname === '/emulator'
  const isMode = location.pathname === '/method'

  let stepIndex = 0
  if (isMode) stepIndex = 1
  else if (isEmulatorConfig) stepIndex = 2
  else if (isReview) stepIndex = 3

  const maxSteps = 4
  const totalSteps = maxSteps

  function renderStep() {
    if (isReview) return <ReviewStep onBack={() => navigate(isEmulatorConfig ? '/emulator' : '/setup')} />
    if (isEmulatorConfig) return <EmulatorConfigStep />
    if (isMode) return <ModeStep />
    return <Step1 />
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 p-6 flex flex-col gap-6">

        <div className="flex flex-col items-center gap-1">
          <h1 className="text-slate-200 font-bold text-lg tracking-wide">HOMEPOT Agent</h1>
          <p className="text-slate-500 text-xs">Device Setup</p>
        </div>

        <StepIndicator current={stepIndex} />

        <div className="border-t border-slate-700 pt-4">
          {!isReview && !isMode && !isEmulatorConfig && (
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

          {renderStep()}
        </div>

        <p className="text-center text-slate-600 text-xs">
          Step {stepIndex + 1} of {totalSteps}
        </p>
      </div>
    </div>
  )
}
