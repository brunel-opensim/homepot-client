import React from 'react';
import RoleTabs from './RoleTabs';
import AuthSubmitButton from './AuthSubmitButton';

export default function SignupForm({
  activeTab,
  setActiveTab,
  name,
  setName,
  username,
  setUsername,
  email,
  setEmail,
  password,
  setPassword,
  loading,
  errorMsg,
  successMsg,
  onSubmit, // () => Promise<{success: boolean}>
  onNavigateToSignIn,
}) {
  const activeColor = activeTab === 'ENGINEER' ? 'indigo' : 'teal';

  return (
    <>
      {/* Tab Selector */}
      <RoleTabs activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Signup Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        action={undefined}
      >
        <div className="space-y-4">
          <div className="relative group">
            <input
              name="name"
              autoComplete="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder=" "
              className={`peer w-full px-5 py-4 bg-gray-900/50 border border-gray-600 rounded-xl text-white placeholder-transparent focus:outline-none focus:border-${activeColor}-500 focus:ring-1 focus:ring-${activeColor}-500 transition-all duration-300`}
            />
            <label
              className={`absolute left-4 -top-2.5 bg-gray-900 px-2 text-xs text-gray-400 transition-all duration-300 peer-placeholder-shown:text-base peer-placeholder-shown:text-gray-500 peer-placeholder-shown:top-4 peer-focus:-top-2.5 peer-focus:text-xs peer-focus:text-${activeColor}-400`}
            >
              Full Name
            </label>
          </div>

          <div className="relative group">
            <input
              name="username"
              autoComplete="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder=" "
              className={`peer w-full px-5 py-4 bg-gray-900/50 border border-gray-600 rounded-xl text-white placeholder-transparent focus:outline-none focus:border-${activeColor}-500 focus:ring-1 focus:ring-${activeColor}-500 transition-all duration-300`}
            />
            <label
              className={`absolute left-4 -top-2.5 bg-gray-900 px-2 text-xs text-gray-400 transition-all duration-300 peer-placeholder-shown:text-base peer-placeholder-shown:text-gray-500 peer-placeholder-shown:top-4 peer-focus:-top-2.5 peer-focus:text-xs peer-focus:text-${activeColor}-400`}
            >
              Username
            </label>
          </div>

          <div className="relative group">
            <input
              name="email"
              autoComplete="email"
              type="email"
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
              autoComplete="new-password"
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

          {/* Role selection - Hidden since role is auto-assigned based on tab */}
          {activeTab === 'ENGINEER' && (
            <div className="p-3 bg-indigo-900/20 border border-indigo-700/50 rounded-xl">
              <p className="text-indigo-300 text-sm text-center font-medium">
                Registering as an Engineer (Admin access)
              </p>
            </div>
          )}
          {activeTab === 'CLIENT' && (
            <div className="p-3 bg-teal-900/20 border border-teal-700/50 rounded-xl">
              <p className="text-teal-300 text-sm text-center font-medium">
                Registering as a Client (Device management access)
              </p>
            </div>
          )}

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

          <div className="text-center flex justify-center items-center gap-3 mb-6">
            <span className="text-gray-400 text-sm">Already have an account?</span>
            <button
              onClick={onNavigateToSignIn}
              type="button"
              className={`text-sm font-semibold transition-colors duration-200 ${
                activeTab === 'ENGINEER'
                  ? 'text-indigo-400 hover:text-indigo-300'
                  : 'text-teal-400 hover:text-teal-300'
              }`}
            >
              Sign in
            </button>
          </div>

          <AuthSubmitButton
            activeTab={activeTab}
            loading={loading}
            loadingText="Creating Account..."
          >
            Sign Up
          </AuthSubmitButton>
        </div>
      </form>
    </>
  );
}
