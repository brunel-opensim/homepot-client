import { useEffect, useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { apiBaseUrl } from '../config/api'
import { credentialStorage } from '../services/credentialStorage'
import { bootstrapProvision, checkDeviceName, verifyBootstrapCredentials } from '../services/api'

const EMULATOR_TYPES: { value: string; label: string; deviceType: string; os: string; description: string }[] = [
  { value: 'linux_pos', label: 'Linux POS', deviceType: 'pos_terminal', os: 'Linux 6.8.0 (Debian 12)', description: 'Simulates a Linux-based POS terminal' },
  { value: 'android_pos', label: 'Android POS', deviceType: 'pos_terminal', os: 'Android 14', description: 'Simulates an Android POS tablet' },
]

function formatDeviceType(v: string) {
  return v.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function normalizeOS(platform: string): string | null {
  const value = platform.toLowerCase()
  if (value.includes('android')) return 'android'
  if (value.includes('iphone') || value.includes('ipad') || value.includes('ios')) return 'ios'
  if (value.includes('darwin') || value.includes('mac')) return 'mac'
  if (value.includes('win')) return 'windows'
  if (value.includes('linux')) return 'linux'
  return null
}

function detectBrowserOS(): string {
  const uaData = (navigator as unknown as { userAgentData?: { platform?: string } }).userAgentData
  if (uaData?.platform) {
    const detected = normalizeOS(uaData.platform)
    if (detected) return detected
  }
  const platform = navigator.platform.toLowerCase()
  const ua = navigator.userAgent.toLowerCase()
  if (ua.includes('android')) return 'android'
  if (/iphone|ipad|ipod/.test(ua)) return 'ios'
  const detected = normalizeOS(platform)
  if (detected) return detected
  if (ua.includes('cros')) return 'linux'
  return 'web'
}

async function detectOS(): Promise<string> {
  try {
    const nativePlatform = (await window.electronAPI?.device.dna())?.platform
    if (nativePlatform) {
      const detected = normalizeOS(nativePlatform)
      if (detected) return detected
    }
  } catch {
    // Fall back to browser detection if the native bridge is unavailable.
  }
  return detectBrowserOS()
}

type SetupStep = { label: string; path?: string }

function StepIndicator({ current, steps }: { current: number; steps: SetupStep[] }) {
  return (
    <nav aria-label="Setup progress" className="flex items-center justify-center gap-2 w-full">
      {steps.map((step, i) => {
        const content = (
          <>
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
              {step.label}
            </span>
          </>
        )
        const reached = i <= current
        return (
          <div key={step.label} className="flex items-center gap-2">
            {reached && step.path ? (
              <Link
                to={step.path}
                aria-current={i === current ? 'step' : undefined}
                className="flex flex-col items-center gap-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
              >
                {content}
              </Link>
            ) : (
              <div className="flex flex-col items-center gap-1" aria-disabled="true">
                {content}
              </div>
            )}
            {i < steps.length - 1 && (
              <div className={`w-10 h-0.5 mb-4 ${i < current ? 'bg-emerald-500' : 'bg-slate-700'}`} />
            )}
          </div>
        )
      })}
    </nav>
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
  const [credentialStatus, setCredentialStatus] = useState<'idle' | 'checking' | 'verified' | 'invalid' | 'unavailable'>('idle')
  const [nameStatus, setNameStatus] = useState<'idle' | 'checking' | 'available' | 'taken'>('idle')

  useEffect(() => {
    if (!siteId.trim() || !bootstrapKey.trim()) return
    let cancelled = false
    const timer = setTimeout(async () => {
      setCredentialStatus('checking')
      try {
        const res = await verifyBootstrapCredentials({
          site_id: siteId.trim(),
          bootstrap_key: bootstrapKey.trim(),
        })
        if (!cancelled) setCredentialStatus(res.verified ? 'verified' : 'invalid')
      } catch {
        if (!cancelled) setCredentialStatus('unavailable')
      }
    }, 500)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [siteId, bootstrapKey])

  useEffect(() => {
    if (credentialStatus !== 'verified' || !deviceName.trim()) return
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
  }, [credentialStatus, siteId, bootstrapKey, deviceName])

  const handleNext = async () => {
    const resolvedOs = deviceOs === 'auto' ? await detectOS() : deviceOs
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
            setCredentialStatus('idle')
            setNameStatus('idle')
          }}
          placeholder="Enter your Site ID"
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
        />
        <p className="text-slate-500 text-xs">
          {siteId.trim()
            ? 'Enter the bootstrap key provided by your administrator to verify this site.'
            : 'Provided by your IT administrator.'}
        </p>
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
            setCredentialStatus('idle')
            setNameStatus('idle')
          }}
          placeholder="Enter your Bootstrap Key"
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
        />
        <p className="text-slate-500 text-xs">
          Provided by your IT administrator. For emulator testing use the dev key: <span className="text-slate-400">homepot-dev-emulator-key</span>.
        </p>
        {credentialStatus === 'checking' && (
          <p className="text-slate-500 text-xs">Checking site credentials...</p>
        )}
        {credentialStatus === 'verified' && (
          <p className="text-emerald-500 text-xs">✓ Site credentials verified</p>
        )}
        {credentialStatus === 'invalid' && (
          <p className="text-red-400 text-xs">✗ Site ID or bootstrap key is incorrect.</p>
        )}
        {credentialStatus === 'unavailable' && (
          <p className="text-amber-400 text-xs">Unable to verify site credentials. Please try again.</p>
        )}
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
            setNameStatus('idle')
          }}
          placeholder="e.g. Device-001"
          disabled={credentialStatus !== 'verified'}
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
        />
        {credentialStatus !== 'verified' && (
          <p className="text-slate-500 text-xs">Verify the Site ID and bootstrap key first.</p>
        )}
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
        disabled={credentialStatus !== 'verified' || nameStatus !== 'available' || !deviceType}
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
  const selectedEmulator = EMULATOR_TYPES.find(t => t.value === emulatorType)
  const emulatorAvailable = Boolean(window.electronAPI?.emulator)

  async function handleComplete() {
    setLoading(true)
    setError('')
    try {
      if (useEmulator) {
        if (!window.electronAPI?.emulator) {
          throw new Error('Emulator launch requires the Electron desktop app.')
        }
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
          <span className="text-slate-400">Setup Method</span>
          <span className="text-slate-200 font-medium">{useEmulator ? 'Emulator' : 'Physical device'}</span>
        </div>
        {useEmulator && (
          <div className="flex justify-between">
            <span className="text-slate-400">Emulator Profile</span>
            <span className="text-slate-200 font-medium">{selectedEmulator?.label ?? emulatorType}</span>
          </div>
        )}
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
          disabled={loading || (useEmulator === true && !emulatorAvailable)}
          className="flex-[2] py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />{useEmulator ? 'Launching...' : 'Provisioning...'}</>
          ) : (
            useEmulator ? 'Launch Emulator' : 'Complete Setup'
          )}
        </button>
      </div>
      {useEmulator && !emulatorAvailable && (
        <p className="w-full text-left text-xs text-amber-400">
          Emulator launch requires the Electron desktop app. Browser mode cannot start a local emulator process.
        </p>
      )}
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
    setSetupState({ ...setupState, deviceType: selected.deviceType, deviceOs: selected.os })
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

  const handleNext = () => {
    if (useEmulator === null) return
    if (useEmulator) {
      if (!EMULATOR_TYPES.find(t => t.value === emulatorType)) {
        setEmulatorType(EMULATOR_TYPES[0].value)
      }
      navigate('/emulator')
    } else {
      navigate('/setup/review')
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
          onClick={() => setUseEmulator(false)}
          aria-pressed={useEmulator === false}
          className={`w-full text-left px-4 py-4 rounded-lg border-2 transition-colors ${
            useEmulator === false ? 'border-emerald-500 bg-slate-700' : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-slate-200 font-medium text-sm">Set up a real device</span>
            {useEmulator === false && <span className="text-emerald-400 text-sm">✓</span>}
          </div>
          <p className="text-slate-400 text-xs mt-1">Provision this physical device with the verified setup details.</p>
        </button>

        <button
          onClick={() => setUseEmulator(true)}
          aria-pressed={useEmulator === true}
          className={`w-full text-left px-4 py-4 rounded-lg border-2 transition-colors ${
            useEmulator ? 'border-emerald-500 bg-slate-700' : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-slate-200 font-medium text-sm">Launch emulated device</span>
            {useEmulator && <span className="text-emerald-400 text-sm">✓</span>}
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
          disabled={useEmulator === null}
          className="flex-[2] py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors"
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
  const { setupState, useEmulator } = useApp()
  const isReview = location.pathname === '/setup/review'
  const isEmulatorConfig = location.pathname === '/emulator'
  const isMode = location.pathname === '/method'
  const requiresSetup = isMode || isEmulatorConfig || isReview
  const requiresMethod = isEmulatorConfig || isReview
  const setupComplete = Boolean(
    setupState.siteId.trim()
    && setupState.bootstrapKey.trim()
    && setupState.deviceName.trim()
    && setupState.deviceType
    && setupState.deviceOs,
  )

  useEffect(() => {
    if (requiresSetup && !setupComplete) {
      navigate('/setup', { replace: true })
    } else if (requiresMethod && (useEmulator === null || (isEmulatorConfig && !useEmulator))) {
      navigate('/method', { replace: true })
    }
  }, [isEmulatorConfig, navigate, requiresMethod, requiresSetup, setupComplete, useEmulator])

  let stepIndex = 0
  if (isMode) stepIndex = 1
  else if (isEmulatorConfig) stepIndex = 2
  else if (isReview) stepIndex = useEmulator ? 3 : 2

  const steps = useEmulator === true
    ? [
        { label: 'Device Setup', path: '/setup' },
        { label: 'Method', path: '/method' },
        { label: 'Emulator', path: '/emulator' },
        { label: 'Complete', path: '/setup/review' },
      ]
    : useEmulator === false
      ? [
          { label: 'Device Setup', path: '/setup' },
          { label: 'Method', path: '/method' },
          { label: 'Complete', path: '/setup/review' },
        ]
      : [
          { label: 'Device Setup', path: '/setup' },
          { label: 'Method', path: '/method' },
          { label: 'Configuration' },
          { label: 'Complete' },
        ]

  function renderStep() {
    if (isReview) return <ReviewStep onBack={() => navigate(useEmulator ? '/emulator' : '/method')} />
    if (isEmulatorConfig) return <EmulatorConfigStep />
    if (isMode) return <ModeStep />
    return <Step1 />
  }

  if (
    (requiresSetup && !setupComplete)
    || (requiresMethod && (useEmulator === null || (isEmulatorConfig && !useEmulator)))
  ) return null

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 p-6 flex flex-col gap-6">

        <div className="flex flex-col items-center gap-1">
          <h1 className="text-slate-200 font-bold text-lg tracking-wide">HOMEPOT Agent</h1>
          <p className="text-slate-500 text-xs">Device Setup</p>
        </div>

        <StepIndicator current={stepIndex} steps={steps} />

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
          Step {stepIndex + 1} of {steps.length}
        </p>
      </div>
    </div>
  )
}
