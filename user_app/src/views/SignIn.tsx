import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiBaseUrl } from '../config/api'

export default function SignIn() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const isDev = import.meta.env.DEV

  async function handleLogin() {
    setLoading(true)
    setError('')
    try {
      if (isDev && email === 'dev@test.com') {
        await new Promise(r => setTimeout(r, 500))
        navigate('/setup/review')
        return
      }

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
      navigate('/setup/review')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 p-6 flex flex-col gap-6">

        <div className="flex flex-col items-center gap-1">
          <h1 className="text-slate-200 font-bold text-lg tracking-wide">HOMEPOT Agent</h1>
          <p className="text-slate-500 text-xs">Sign In</p>
        </div>

        <div className="flex items-center justify-center gap-2 w-full">
          {['Device Setup', 'SSO Login', 'Complete'].map((label, i) => (
            <div key={label} className="flex items-center gap-2">
              <div className="flex flex-col items-center gap-1">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors ${
                  i < 1 ? 'bg-emerald-500 border-emerald-500 text-white'
                  : i === 1 ? 'border-emerald-500 text-emerald-400 bg-slate-900'
                  : 'border-slate-600 text-slate-500 bg-slate-900'
                }`}>
                  {i < 1 ? '✓' : i + 1}
                </div>
                <span className={`text-xs ${i === 1 ? 'text-emerald-400' : 'text-slate-500'}`}>{label}</span>
              </div>
              {i < 2 && <div className={`w-10 h-0.5 mb-4 ${i < 1 ? 'bg-emerald-500' : 'bg-slate-700'}`} />}
            </div>
          ))}
        </div>

        <div className="border-t border-slate-700 pt-4">
          <div className="flex flex-col gap-5 w-full">
            <div className="text-center">
              <h2 className="text-slate-200 font-semibold text-base">Sign in to your account</h2>
              <p className="text-slate-400 text-xs mt-1">Use your credentials to authorise device enrolment.</p>
            </div>

            {error && (
              <div className="p-3 bg-red-900/50 border border-red-700 rounded-lg text-sm text-red-200">{error}</div>
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
                <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Signing in...</>
              ) : (
                '🔐  Sign In'
              )}
            </button>

            {isDev && (
              <button
                onClick={() => { setEmail('dev@test.com'); setPassword('dev'); handleLogin() }}
                disabled={loading}
                className="w-full py-2 rounded-lg border border-dashed border-slate-600 text-slate-500 hover:text-slate-300 text-xs transition-colors"
              >
                ⚡ Dev: Skip Login
              </button>
            )}

            <button
              onClick={() => navigate('/setup')}
              disabled={loading}
              className="w-full py-2 rounded-lg border border-slate-600 text-slate-400 hover:text-slate-200 text-sm transition-colors"
            >
              ← Back
            </button>
          </div>
        </div>

        <p className="text-center text-slate-600 text-xs">Step 2 of 3</p>
      </div>
    </div>
  )
}
