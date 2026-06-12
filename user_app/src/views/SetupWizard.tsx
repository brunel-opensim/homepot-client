import { useState } from 'react'
import { useApp } from '../context/AppContext'

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

function Step1({ siteId, setSiteId, deviceName, setDeviceName, onNext }: {
  siteId: string
  setSiteId: (v: string) => void
  deviceName: string
  setDeviceName: (v: string) => void
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
          Device Name <span className="text-emerald-500 font-normal">*</span>
        </label>
        <input
          type="text"
          value={deviceName}
          onChange={e => setDeviceName(e.target.value)}
          placeholder="e.g. Kasi-Laptop"
          className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
        />
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
  const [loading, setLoading] = useState(false)

  function handleSSO() {
    setLoading(true)
    setTimeout(() => {
      setLoading(false)
      onNext()
    }, 1500)
  }

  return (
    <div className="flex flex-col gap-5 w-full">
      <div className="text-center">
        <h2 className="text-slate-200 font-semibold text-base">Sign in to your account</h2>
        <p className="text-slate-400 text-xs mt-1">Use your company SSO credentials.</p>
      </div>

      <div className="w-16 h-16 rounded-full bg-slate-700 border-2 border-slate-600 flex items-center justify-center mx-auto">
        <span className="text-3xl">🔐</span>
      </div>

      <button
        onClick={handleSSO}
        disabled={loading}
        className="w-full py-3 rounded-lg bg-teal-600 hover:bg-teal-500 disabled:opacity-60 text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Signing in...
          </>
        ) : (
          '🔐  Login with SSO'
        )}
      </button>

      <button
        onClick={onBack}
        className="w-full py-2 rounded-lg border border-slate-600 text-slate-400 hover:text-slate-200 text-sm transition-colors"
      >
        ← Back
      </button>
    </div>
  )
}

function Step3({ siteId, deviceName, onComplete }: {
  siteId: string
  deviceName: string
  onComplete: () => void
}) {
  const [loading, setLoading] = useState(false)

  async function handleComplete() {
    setLoading(true)
    try {
      const deviceId = 'dev-' + Date.now()
      const reqBody = {
        device_id: deviceId,
        site_id: siteId,
        name: deviceName || 'My Device',
        device_type: 'physical_terminal',
        enrollment_method: 'self-enrolled'
      }

      const response = await fetch(`http://localhost:8000/api/v1/devices/sites/${siteId}/devices`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(reqBody)
      })

      if (!response.ok) {
        throw new Error('Failed to register device via API')
      }

      const data = await response.json()
      
      localStorage.setItem('homepot_token', data.device_id || deviceId)
      localStorage.setItem('homepot_site_id', siteId)
      localStorage.setItem('homepot_device_name', deviceName || 'My Device')
      localStorage.setItem('homepot_enrollment_method', 'self-enrolled')
      
      setLoading(false)
      onComplete()
    } catch (error) {
      console.error(error)
      // Fallback for UI demonstration 
      localStorage.setItem('homepot_token', 'mock-token-' + Date.now())
      localStorage.setItem('homepot_site_id', siteId)
      localStorage.setItem('homepot_device_name', deviceName || 'My Device')
      localStorage.setItem('homepot_enrollment_method', 'self-enrolled')
      
      setLoading(false)
      onComplete()
    }
  }

  return (
    <div className="flex flex-col gap-5 w-full items-center text-center">
      <div className="w-16 h-16 rounded-full bg-emerald-900 border-2 border-emerald-500 flex items-center justify-center">
        <span className="text-3xl">✓</span>
      </div>

      <div>
        <h2 className="text-slate-200 font-semibold text-base">All set!</h2>
        <p className="text-slate-400 text-xs mt-1">Your device is ready to be provisioned.</p>
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
      </div>

      <button
        onClick={handleComplete}
        disabled={loading}
        className="w-full py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
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
  )
}

export default function SetupWizard() {
  const { setCurrentView, setIsProvisioned } = useApp()
  const [step, setStep] = useState(0)
  const [siteId, setSiteId] = useState('')
  const [deviceName, setDeviceName] = useState('')

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
          {step === 0 && (
            <Step1
              siteId={siteId}
              setSiteId={setSiteId}
              deviceName={deviceName}
              setDeviceName={setDeviceName}
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
