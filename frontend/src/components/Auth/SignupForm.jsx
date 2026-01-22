import React from 'react';

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
      <div className="text-center mb-8">
        <div className="flex rounded-xl bg-gray-800/50 p-1 border border-gray-700/50">
          <button
            type="button"
            onClick={() => setActiveTab('ENGINEER')}
            className={`flex-1 py-3 px-6 text-sm font-bold rounded-lg transition-all duration-300 flex items-center justify-center gap-2 ${
              activeTab === 'ENGINEER'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20 ring-1 ring-white/10'
                : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
            }`}
          >
            <svg
              className={`w-4 h-4 ${activeTab === 'ENGINEER' ? 'text-indigo-200' : 'text-gray-500'}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
              />
            </svg>
            ENGINEER
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('CLIENT')}
            className={`flex-1 py-3 px-6 text-sm font-bold rounded-lg transition-all duration-300 flex items-center justify-center gap-2 ${
              activeTab === 'CLIENT'
                ? 'bg-teal-600 text-white shadow-lg shadow-teal-500/20 ring-1 ring-white/10'
                : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
            }`}
          >
            <svg
              className={`w-4 h-4 ${activeTab === 'CLIENT' ? 'text-teal-200' : 'text-gray-500'}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
              />
            </svg>
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

          <button
            type="submit"
            disabled={loading}
            className={`w-full font-bold py-4 px-6 rounded-xl transition-all duration-300 transform hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 shadow-lg disabled:opacity-60 disabled:cursor-not-allowed flex justify-center items-center gap-2 ${
              activeTab === 'ENGINEER'
                ? 'bg-indigo-600 hover:bg-indigo-500 focus:ring-indigo-500 shadow-indigo-900/20'
                : 'bg-teal-600 hover:bg-teal-500 focus:ring-teal-500 shadow-teal-900/20'
            }`}
          >
            {loading ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-2 h-5 w-5 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                Creating Account...
              </>
            ) : (
              'Sign Up'
            )}
          </button>
        </div>
      </form>
    </>
  );
}
