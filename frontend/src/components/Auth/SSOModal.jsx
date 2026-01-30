import React, { useState } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import api from '@/services/api';

export default function SSOModal({ open, onOpenChange }) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleGoogleLogin = async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await api.auth.googleLogin();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      } else {
        setError('Failed to get authentication URL.');
        setIsLoading(false);
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'SSO is currently unavailable.';
      setError(detail);
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0 bg-gradient-to-br from-gray-900 via-gray-900 to-gray-950 backdrop-blur-2xl border border-gray-700/50 shadow-2xl shadow-black/50 max-w-md overflow-hidden rounded-2xl">
        <DialogTitle className="sr-only">SSO Configuration</DialogTitle>

        {/* Layered background effects */}
        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/8 via-transparent to-blue-600/8 pointer-events-none" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-cyan-400/10 via-transparent to-transparent pointer-events-none" />

        {/* Corner accent with enhanced glow */}
        <div className="absolute -top-20 -right-20 w-60 h-60 bg-gradient-to-br from-cyan-500/25 via-cyan-400/10 to-transparent rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 -left-32 w-64 h-64 bg-gradient-to-tr from-blue-600/15 via-transparent to-transparent rounded-full blur-3xl pointer-events-none" />

        {/* Inner border glow */}
        <div className="absolute inset-[1px] rounded-2xl bg-gradient-to-br from-white/5 to-transparent pointer-events-none" />

        <div className="relative z-10 p-8 space-y-7">
          {/* Header with icon */}
          <div className="flex items-start gap-4">
            <div className="p-3 bg-gradient-to-br from-cyan-500/20 to-cyan-600/10 rounded-xl border border-cyan-500/20 shadow-lg shadow-cyan-500/10">
              <svg
                className="w-6 h-6 text-cyan-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z"
                />
              </svg>
            </div>
            <div className="space-y-1.5 pt-0.5">
              <h2
                className="text-2xl font-bold bg-gradient-to-r from-white via-white to-gray-300 bg-clip-text text-transparent"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                SSO Configuration
              </h2>
              <p
                className="text-gray-400 text-sm tracking-wide"
                style={{ fontFamily: "'Inter', sans-serif" }}
              >
                Secure single sign-on authentication
              </p>
            </div>
          </div>

          {/* Elegant divider */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-gray-600/50 to-transparent" />
            <div className="flex items-center gap-1.5 px-2">
              <div className="w-1 h-1 rounded-full bg-cyan-400 shadow-sm shadow-cyan-400/50" />
              <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-sm shadow-cyan-400/50" />
              <div className="w-1 h-1 rounded-full bg-cyan-400 shadow-sm shadow-cyan-400/50" />
            </div>
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-gray-600/50 to-transparent" />
          </div>

          {/* Error message */}
          {error && (
            <div className="p-4 bg-red-950/60 border border-red-500/30 rounded-xl text-red-300 text-sm text-center backdrop-blur-sm flex items-center justify-center gap-2">
              <svg
                className="w-4 h-4 flex-shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
              {error}
            </div>
          )}

          {/* Google SSO Button */}
          <button
            onClick={handleGoogleLogin}
            disabled={isLoading}
            className="w-full group relative overflow-hidden rounded-xl focus:outline-none focus:ring-2 focus:ring-cyan-400/50 focus:ring-offset-2 focus:ring-offset-gray-900"
          >
            {/* Button outer glow on hover */}
            <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500/30 via-blue-500/30 to-cyan-500/30 rounded-xl blur-lg opacity-0 group-hover:opacity-100 transition-opacity duration-500 ease-out" />

            <div
              className={`
                relative bg-white rounded-xl p-4
                flex items-center justify-center gap-3
                border-2 border-gray-200 shadow-lg
                transition-[border-color,box-shadow,transform] duration-300 ease-out
                group-hover:border-cyan-400/70 group-hover:shadow-xl group-hover:shadow-cyan-500/15 group-hover:scale-[1.01]
                ${isLoading ? 'opacity-80 cursor-wait' : 'cursor-pointer'}
              `}
            >
              {/* Shine effect - CSS only */}
              <div className="absolute inset-0 rounded-xl overflow-hidden pointer-events-none">
                <div className="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-700 ease-out bg-gradient-to-r from-transparent via-cyan-300/40 to-transparent" />
              </div>

              {isLoading ? (
                <div className="relative z-10 flex items-center gap-3">
                  <div className="w-5 h-5 border-[3px] border-gray-200 border-t-cyan-500 rounded-full animate-spin" />
                  <span
                    className="text-gray-600 font-semibold"
                    style={{ fontFamily: "'Inter', sans-serif" }}
                  >
                    Authenticating...
                  </span>
                </div>
              ) : (
                <>
                  <svg className="relative z-10 w-5 h-5" viewBox="0 0 24 24">
                    <path
                      fill="#4285F4"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    />
                  </svg>
                  <span
                    className="relative z-10 text-gray-700 font-semibold tracking-tight"
                    style={{ fontFamily: "'Inter', sans-serif" }}
                  >
                    Continue with Google
                  </span>
                  <svg
                    className="relative z-10 w-4 h-4 text-gray-400 transition-transform duration-300 ease-out group-hover:translate-x-1"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </>
              )}
            </div>
          </button>

          {/* Security info with shield icon */}
          <div className="flex items-start gap-3.5 p-4 bg-gradient-to-br from-cyan-500/8 to-blue-500/5 border border-cyan-500/15 rounded-xl backdrop-blur-sm">
            <div className="p-2 bg-cyan-500/10 rounded-lg">
              <svg
                className="w-4 h-4 text-cyan-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
                />
              </svg>
            </div>
            <div className="space-y-1">
              <p
                className="text-xs text-gray-300 font-medium"
                style={{ fontFamily: "'Inter', sans-serif" }}
              >
                Enterprise Security
              </p>
              <p
                className="text-xs text-gray-500 leading-relaxed"
                style={{ fontFamily: "'Inter', sans-serif" }}
              >
                Protected with end-to-end encryption and OAuth 2.0 protocol
              </p>
            </div>
          </div>

          {/* Footer */}
          <div className="text-center pt-5 border-t border-gray-800/50">
            <p className="text-xs text-gray-500" style={{ fontFamily: "'Inter', sans-serif" }}>
              By continuing, you agree to HomePot's{' '}
              <span className="text-gray-400 hover:text-cyan-400 cursor-pointer transition-colors">
                Terms of Service
              </span>
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
