import React from 'react';
import Dropdown from '@/components/ui/dropdown';

export default function SignupForm({
  activeTab,
  setActiveTab,
  name,
  setName,
  email,
  setEmail,
  password,
  setPassword,
  role,
  setRole,
  loading,
  errorMsg,
  successMsg,
  onSubmit, // () => Promise<{success: boolean}>
  onNavigateToSignIn,
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

      {/* Signup Form */}
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
              name="name"
              autoComplete="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Full Name"
              className="w-full px-4 py-4 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all duration-200"
            />
          </div>

          <div>
            <input
              name="email"
              autoComplete="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              className="w-full px-4 py-4 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all duration-200"
            />
          </div>

          <div>
            <input
              name="password"
              autoComplete="new-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="w-full px-4 py-4 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all duration-200"
            />
          </div>

          {/* Role selection - Only show for Client tab, Engineer/Admin is auto-assigned */}
          {activeTab === 'CLIENT' && (
            <div>
              <Dropdown
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="Select Role"
                options={[
                  { label: 'User', value: 'User' },
                  { label: 'Manager', value: 'Manager' },
                ]}
              />
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

          <div className="text-center flex justify-center items-center gap-2">
            <button
              type="button"
              className={`text-sm transition-colors duration-200 ${
                activeTab === 'ENGINEER'
                  ? 'text-teal-400 hover:text-teal-300 font-bold'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              Sign up with SSO
            </button>

            <div className="h-4 w-px bg-gray-600"></div>

            <button
              onClick={onNavigateToSignIn}
              type="button"
              className="text-teal-400 hover:text-teal-300 text-sm transition-colors duration-200"
            >
              Sign in
            </button>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-teal-600 hover:bg-teal-700 text-white font-medium py-4 px-6 rounded-lg transition-all duration-200 transform hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? 'Creating Account…' : 'Sign Up'}
          </button>
        </div>
      </form>
    </>
  );
}
