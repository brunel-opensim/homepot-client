import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'

export default function SignIn() {
  const navigate = useNavigate()
  const { setupState, setSetupState } = useApp()
  const [bootstrapKey, setBootstrapKey] = useState(setupState.bootstrapKey)

  function handleNext() {
    if (!bootstrapKey.trim()) return
    setSetupState({ ...setupState, bootstrapKey: bootstrapKey.trim() })
    navigate('/setup/review')
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 p-6 flex flex-col gap-6">
        <div className="flex flex-col items-center gap-1">
          <h1 className="text-slate-200 font-bold text-lg tracking-wide">HOMEPOT Agent</h1>
          <p className="text-slate-500 text-xs">Bootstrap Key</p>
        </div>
        <div className="flex items-center justify-center gap-2 w-full">
          {['Device Setup', 'Method', 'Bootstrap Key', 'Complete'].map((label, i) => (
            <div key={label} className="flex items-center gap-2">
              <div className="flex flex-col items-center gap-1">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors ${
                  i < 2 ? 'bg-emerald-500 border-emerald-500 text-white'
                  : i === 2 ? 'border-emerald-500 text-emerald-400 bg-slate-900'
                  : 'border-slate-600 text-slate-500 bg-slate-900'
                }`}>
                  {i < 2 ? '✓' : i + 1}
                </div>
                <span className={`text-xs ${i === 2 ? 'text-emerald-400' : 'text-slate-500'}`}>{label}</span>
              </div>
              {i < 3 && <div className={`w-10 h-0.5 mb-4 ${i < 2 ? 'bg-emerald-500' : 'bg-slate-700'}`} />}
            </div>
          ))}
        </div>
        <div className="border-t border-slate-700 pt-4">
          <div className="flex flex-col gap-5 w-full">
            <div className="text-center">
              <h2 className="text-slate-200 font-semibold text-base">Enter bootstrap key</h2>
              <p className="text-slate-400 text-xs mt-1">Use the key provided by your administrator to enrol this device.</p>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-slate-300 text-sm font-medium">Bootstrap Key</label>
              <input
                type="text"
                value={bootstrapKey}
                onChange={e => setBootstrapKey(e.target.value)}
                placeholder="Paste your bootstrap key"
                className="w-full px-3 py-2.5 rounded-lg bg-slate-700 border border-slate-600 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-teal-500 transition-colors font-mono tracking-wider"
              />
              <p className="text-slate-500 text-xs mt-1">Provided by your IT administrator for site-level enrolment.</p>
            </div>
            <button onClick={handleNext} disabled={!bootstrapKey.trim()} className="w-full py-3 rounded-lg bg-teal-600 hover:bg-teal-500 disabled:opacity-60 text-white font-semibold text-sm transition-colors">
              Next →
            </button>
            {import.meta.env.DEV && (
              <button
                onClick={() => {
                  setBootstrapKey('dev-bootstrap-key')
                  handleNext()
                }}
                className="w-full py-2 rounded-lg border border-dashed border-slate-600 text-slate-500 hover:text-slate-300 text-xs transition-colors"
              >
                Dev: Skip Bootstrap Key
              </button>
            )}
            <button onClick={() => navigate('/method')} className="w-full py-2 rounded-lg border border-slate-600 text-slate-400 hover:text-slate-200 text-sm transition-colors">
              Back
            </button>
          </div>
        </div>
        <p className="text-center text-slate-600 text-xs">Step 3 of 4</p>
      </div>
    </div>
  )
}
