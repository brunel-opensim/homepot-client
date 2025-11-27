// frontend/src/components/Auth/LoginForm.jsx
import React from 'react';

export default function LoginForm({
  activeTab,
  setActiveTab,
  email,
  setEmail,
  password,
  setPassword,
  loading,
  errorMsg,
  onSubmit, // () => Promise<{success: boolean}>
  onNavigateToSignUp,
}) {
  return (
    <>
      {/* Tab Selector */}
      <div className="text-center mb-6">
        <div className="flex rounded-lg gap-4 overflow-hidden">
          <button
            type="button"
            onClick={() => setActiveTab('ENGINEER')}
            className={`flex-1 py-3 px-6 text-sm font-semibold rounded-lg transition-all duration-200 ${
              activeTab === 'ENGINEER'
                ? 'bg-teal-600 text-white border border-teal-400'
                : 'bg-gray-800 text-gray-400 hover:text-gray-300 hover:bg-gray-700'
            }`}
          >
            ENGINEER
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('CLIENT')}
            className={`flex-1 py-3 px-6 text-sm font-semibold rounded-lg transition-all duration-200 ${
              activeTab === 'CLIENT'
                ? 'bg-teal-600 text-white border border-teal-400'
                : 'bg-gray-800 text-gray-400 hover:text-gray-300 hover:bg-gray-700'
            }`}
          >
            CLIENT
          </button>
        </div>
      </div>

      {/* Login Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        action={undefined}
      >
        <div className="space-y-6">
          <div>
            <input
              name="email"
              autoComplete="username"
              type="text"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              className="w-full px-4 py-4 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all duration-200"
            />
          </div>

          <div>
            <input
              name="password"
              autoComplete="current-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="w-full px-4 py-4 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all duration-200"
            />
          </div>

          {errorMsg && (
            <div className="text-center p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-300 text-sm">
              {errorMsg}
            </div>
          )}

          <div className="text-center flex justify-center items-center mb-4 gap-2">
            <button
              type="button"
              className="text-teal-400 hover:text-teal-300 text-sm transition-colors duration-200"
            >
              Sign in with SSO
            </button>

            <div className="h-4 w-px bg-gray-600"></div>

            <button
              onClick={onNavigateToSignUp}
              type="button"
              className="text-teal-400 hover:text-teal-300 text-sm transition-colors duration-200"
            >
              Sign up
            </button>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-teal-600 hover:bg-teal-700 text-white font-medium py-4 px-6 rounded-lg transition-all duration-200 transform hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in…' : 'Log In'}
          </button>
        </div>
      </form>
    </>
  );
}
