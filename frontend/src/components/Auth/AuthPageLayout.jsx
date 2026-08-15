import React from 'react';

export default function AuthPageLayout({
  activeColor,
  headingClassName = 'text-5xl',
  subtitle,
  sessionMsg,
  children,
  footer,
}) {
  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background Ambient Glow */}
      <div
        className={`absolute top-0 left-0 w-full h-full bg-gradient-to-br from-${activeColor}-900/10 to-transparent pointer-events-none transition-colors duration-500`}
      ></div>
      <div
        className={`absolute -top-40 -right-40 w-96 h-96 bg-${activeColor}-600/20 rounded-full blur-3xl transition-colors duration-500`}
      ></div>
      <div
        className={`absolute -bottom-40 -left-40 w-96 h-96 bg-${activeColor}-600/20 rounded-full blur-3xl transition-colors duration-500`}
      ></div>

      <div className="w-full max-w-md relative z-10">
        <div
          className={`bg-gray-900/90 backdrop-blur-xl border border-${activeColor}-900/50 rounded-2xl p-8 shadow-2xl shadow-${activeColor}-900/20 transition-all duration-300`}
        >
          <div className="text-center mb-10">
            <h1
              className={`${headingClassName} font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-${activeColor}-200 mb-6 tracking-tight transition-all duration-300`}
            >
              HOMEPOT
            </h1>

            <p className="text-gray-400 mb-4 text-sm font-light">{subtitle}</p>

            {sessionMsg && (
              <div className="mb-4 p-4 bg-yellow-900/20 border border-yellow-700/50 rounded-xl text-yellow-200 text-sm flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                {sessionMsg}
              </div>
            )}
          </div>

          {children}

          {footer && <div className="mt-8 text-center space-y-2">{footer}</div>}
        </div>
      </div>
    </div>
  );
}
