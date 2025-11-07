import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

const NotFound = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated } = useAuth();
  const [countdown, setCountdown] = useState(10);

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          // Redirect to dashboard if authenticated, otherwise to home
          navigate(isAuthenticated ? '/dashboard' : '/login', { replace: true });
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [navigate, isAuthenticated]);

  const handleGoBack = () => {
    if (window.history.length > 2) {
      navigate(-1);
    } else {
      navigate(isAuthenticated ? '/dashboard' : '/');
    }
  };

  const handleGoHome = () => {
    navigate(isAuthenticated ? '/dashboard' : '/');
  };

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-4">
      <div className="max-w-2xl w-full text-center">
        {/* 404 Animation */}
        <div className="mb-8">
          <h1 className="text-9xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-teal-400 via-cyan-500 to-blue-500 animate-pulse">
            404
          </h1>
        </div>

        {/* Error Message */}
        <div className="bg-gray-900/90 backdrop-blur-sm border border-gray-700/50 rounded-lg p-8 shadow-2xl">
          <div className="mb-6">
            <svg
              className="w-20 h-20 mx-auto text-teal-500 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>

            <h2 className="text-3xl font-bold text-white mb-3">Page Not Found</h2>

            <p className="text-gray-400 text-lg mb-2">
              Oops! The page you're looking for doesn't exist.
            </p>

            <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 mt-4 mb-6">
              <p className="text-gray-500 text-sm break-all">
                <span className="text-gray-400 font-semibold">Requested URL:</span>
                <br />
                <code className="text-teal-400">{location.pathname}</code>
              </p>
            </div>

            <p className="text-gray-500 text-sm">
              The URL you entered might be incorrect, or the page may have been moved or deleted.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="space-y-3">
            <button
              onClick={handleGoHome}
              className="w-full bg-teal-600 hover:bg-teal-700 text-white font-medium py-3 px-6 rounded-lg transition-all duration-200 transform hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:ring-offset-gray-900"
            >
              {isAuthenticated ? 'Go to Dashboard' : 'Go to Home'}
            </button>

            <button
              onClick={handleGoBack}
              className="w-full bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium py-3 px-6 rounded-lg transition-all duration-200 transform hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-gray-600 focus:ring-offset-2 focus:ring-offset-gray-900"
            >
              Go Back
            </button>
          </div>

          {/* Auto Redirect Notice */}
          <div className="mt-6 pt-6 border-t border-gray-700">
            <p className="text-gray-500 text-sm">
              Auto redirecting in{' '}
              <span className="inline-block min-w-[1.5rem] text-teal-400 font-bold text-lg">
                {countdown}
              </span>{' '}
              {countdown === 1 ? 'second' : 'seconds'}...
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6">
          <p className="text-gray-600 text-xs">HOMEPOT Unified Client - Error 404</p>
        </div>
      </div>
    </div>
  );
};

export default NotFound;
