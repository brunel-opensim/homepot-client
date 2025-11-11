import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import Dropdown from '@/components/ui/dropdown';
import api from '@/services/api';
import { useAuth } from '@/hooks/useAuth';

const Signup = () => {
  const [activeTab, setActiveTab] = useState('ENGINEER');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [sessionMsg, setSessionMsg] = useState(null);

  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated } = useAuth();

  // Show session expiry message if redirected from protected route
  useEffect(() => {
    if (location.state?.message) {
      setSessionMsg(location.state.message);
      // Clear the message after 5 seconds
      const timer = setTimeout(() => setSessionMsg(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [location]);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleSignUp = async (e) => {
    if (e && typeof e.preventDefault === 'function') e.preventDefault();

    setErrorMsg(null);

    // Validation
    if (!email || !password || !name || !role) {
      setErrorMsg('Please fill in all fields.');
      return;
    }

    if (password.length < 6) {
      setErrorMsg('Password must be at least 6 characters long.');
      return;
    }

    setLoading(true);
    try {
      // TODO: Implement actual signup API call
      const result = await api.auth.signup({ email, password, name, role });

      // Placeholder for now
      console.log('Signup attempt:', { email, password, name, role, activeTab });

      if (result.success) {
        // Always navigate to dashboard after successful login
        navigate('/login', { replace: true });
      } else {
        setErrorMsg(result.error || 'Failed to signup. Please try again.');
      }
    } catch (err) {
      setErrorMsg(err?.message || 'An unexpected error occurred.');
      console.error('Signup error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleNavigateToSignIn = () => {
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-4">
      {/* Signup Card */}
      <div className="w-full max-w-md">
        <div className="bg-gray-900/90 backdrop-blur-sm border border-gray-700/50 rounded-lg p-8 shadow-2xl">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-white mb-6 tracking-wider">HOMEPOT</h1>

            {/* Session expiry message */}
            {sessionMsg && (
              <div className="mb-4 p-3 bg-yellow-900/50 border border-yellow-700 rounded-lg text-yellow-300 text-sm">
                {sessionMsg}
              </div>
            )}

            {/* Tab Selector */}
            <div className="flex rounded-lg gap-4 overflow-hidden mb-6">
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
              handleSignUp(e);
            }}
            action={undefined}
          >
            <div className="space-y-6">
              {/* Name Input */}
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

              {/* Email Input */}
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

              {/* Password Input */}
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

              {/* Role Input */}
              <Dropdown
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="Select Role"
                options={[
                  { label: 'User', value: 'User' },
                  { label: 'Admin', value: 'Admin' },
                ]}
              />

              {/* Show error message */}
              {errorMsg && (
                <div className="text-center p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-300 text-sm">
                  {errorMsg}
                </div>
              )}

              {/* SSO Link and Sign In */}
              <div className="text-center flex justify-center items-center gap-2">
                <button
                  type="button"
                  className="text-teal-400 hover:text-teal-300 text-sm transition-colors duration-200"
                >
                  Sign up with SSO
                </button>

                {/* Vertical divider */}
                <div className="h-4 w-px bg-gray-600"></div>

                <button
                  onClick={handleNavigateToSignIn}
                  type="button"
                  className="text-teal-400 hover:text-teal-300 text-sm transition-colors duration-200"
                >
                  Sign in
                </button>
              </div>

              {/* Signup Button */}
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-teal-600 hover:bg-teal-700 text-white font-medium py-4 px-6 rounded-lg transition-all duration-200 transform hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? 'Creating Account…' : 'Sign Up'}
              </button>
            </div>
          </form>

          {/* Two-factor Authentication Notice */}
          <div className="mt-6 text-center">
            <p className="text-gray-400 text-sm">Two-factor authentication required</p>
            <p className="text-gray-400 text-sm">for Engineers</p>
          </div>

          {/* Footer */}
          <div className="mt-8 text-center">
            <p className="text-gray-500 text-xs">Powered by HOMEPOT Unified Client</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Signup;
