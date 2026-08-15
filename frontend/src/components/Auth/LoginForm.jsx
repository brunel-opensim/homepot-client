// frontend/src/components/Auth/LoginForm.jsx
import React from 'react';
import RoleTabs from './RoleTabs';
import AuthSubmitButton from './AuthSubmitButton';

export default function LoginForm({
  activeTab,
  setActiveTab,
  email,
  setEmail,
  password,
  setPassword,
  loading,
  errorMsg,
  successMsg,
  onSubmit, // () => Promise<{success: boolean}>
  onNavigateToSignUp,
}) {
  const activeColor = activeTab === 'ENGINEER' ? 'indigo' : 'teal';

  return (
    <>
      {/* Tab Selector */}
      <RoleTabs activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Login Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        action={undefined}
      >
        <div className="space-y-5">
          <div className="relative group">
            <input
              name="email"
              autoComplete="username"
              type="text"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder=" "
              className={`peer w-full px-5 py-4 bg-gray-900/50 border border-gray-600 rounded-xl text-white placeholder-transparent focus:outline-none focus:border-${activeColor}-500 focus:ring-1 focus:ring-${activeColor}-500 transition-all duration-300`}
            />
            <label
              className={`absolute left-4 -top-2.5 bg-gray-900 px-2 text-xs text-gray-400 transition-all duration-300 peer-placeholder-shown:text-base peer-placeholder-shown:text-gray-500 peer-placeholder-shown:top-4 peer-focus:-top-2.5 peer-focus:text-xs peer-focus:text-${activeColor}-400`}
            >
              Email Address
            </label>
          </div>

          <div className="relative group">
            <input
              name="password"
              autoComplete="current-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder=" "
              className={`peer w-full px-5 py-4 bg-gray-900/50 border border-gray-600 rounded-xl text-white placeholder-transparent focus:outline-none focus:border-${activeColor}-500 focus:ring-1 focus:ring-${activeColor}-500 transition-all duration-300`}
            />
            <label
              className={`absolute left-4 -top-2.5 bg-gray-900 px-2 text-xs text-gray-400 transition-all duration-300 peer-placeholder-shown:text-base peer-placeholder-shown:text-gray-500 peer-placeholder-shown:top-4 peer-focus:-top-2.5 peer-focus:text-xs peer-focus:text-${activeColor}-400`}
            >
              Password
            </label>
          </div>

          {errorMsg && (
            <div className="text-center p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-300 text-sm">
              {errorMsg}
            </div>
          )}

          {successMsg && (
            <div className="text-center p-3 bg-green-900/50 border border-green-700 rounded-lg text-green-300 text-sm">
              {successMsg}
            </div>
          )}

          {/* SSO Button - More prominent for Engineers (Coming Soon) */}
          {activeTab === 'ENGINEER' && (
            <button
              type="button"
              disabled
              title="Coming Soon"
              className="w-full mb-4 py-3 px-4 bg-gray-800 border border-gray-600 rounded-lg text-gray-500 font-medium text-sm cursor-not-allowed flex items-center justify-center gap-2"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z"
                  clipRule="evenodd"
                />
              </svg>
              Sign in with SSO (Coming Soon)
            </button>
          )}

          <div className="text-center flex justify-center items-center mb-6 gap-3">
            {activeTab === 'CLIENT' && (
              <>
                <button
                  type="button"
                  disabled
                  title="Coming Soon"
                  className="text-gray-500 text-sm cursor-not-allowed hover:text-gray-400 transition-colors"
                >
                  SSO
                </button>
                <div className="h-4 w-px bg-gray-700"></div>
              </>
            )}

            <span className="text-gray-400 text-sm">Don't have an account?</span>
            <button
              onClick={onNavigateToSignUp}
              type="button"
              className={`text-sm font-semibold transition-colors duration-200 ${
                activeTab === 'ENGINEER'
                  ? 'text-indigo-400 hover:text-indigo-300'
                  : 'text-teal-400 hover:text-teal-300'
              }`}
            >
              Sign up
            </button>
          </div>

          <AuthSubmitButton activeTab={activeTab} loading={loading} loadingText="Signing in...">
            Log In
            <svg
              className="w-5 h-5 opacity-70"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M14 5l7 7m0 0l-7 7m7-7H3"
              />
            </svg>
          </AuthSubmitButton>
        </div>
      </form>
    </>
  );
}
