// frontend/src/components/Auth/LoginForm.jsx
import React from 'react';
import AuthSubmitButton from './AuthSubmitButton';

export default function LoginForm({
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
  const activeColor = 'teal';

  return (
    <>
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

          <div className="text-center flex justify-center items-center mb-6 gap-3">
            <span className="text-gray-400 text-sm">Don't have an account?</span>
            <button
              onClick={onNavigateToSignUp}
              type="button"
              className="text-sm font-semibold transition-colors duration-200 text-teal-400 hover:text-teal-300"
            >
              Sign up
            </button>
          </div>

          <AuthSubmitButton activeTab="CLIENT" loading={loading} loadingText="Signing in...">
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
