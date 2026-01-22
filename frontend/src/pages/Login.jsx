// frontend/src/pages/Login.jsx
import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import useAuth from '@/hooks/useAuth';
import LoginForm from '@/components/Auth/LoginForm';

const Login = () => {
  const [activeTab, setActiveTab] = useState('ENGINEER');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [sessionMsg, setSessionMsg] = useState(null);

  const navigate = useNavigate();
  const location = useLocation();
  const { login, clearAuth, isAuthenticated, loading: authLoading } = useAuth();

  // Clear error/success messages when tab changes
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setErrorMsg(null);
    setSuccessMsg(null);
  };

  // Show session expiry message if redirected from protected route
  useEffect(() => {
    if (location.state?.message) {
      setSessionMsg(location.state.message);
      const timer = setTimeout(() => setSessionMsg(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [location]);

  // Redirect if already authenticated (but not while login or auth check is in progress)
  useEffect(() => {
    if (isAuthenticated && !loading && !authLoading) {
      const from = location.state?.from?.pathname || '/dashboard';
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, loading, authLoading, navigate, location]);

  const handleLogin = async (credentials) => {
    setErrorMsg(null);
    setSuccessMsg(null);

    if (!credentials.email || !credentials.password) {
      setErrorMsg('Please provide both email and password.');
      return { success: false };
    }

    setLoading(true);
    try {
      const result = await login(credentials);

      if (result.success) {
        const isAdmin = result.data?.data?.is_admin;

        // Validate role matches selected tab
        if (activeTab === 'ENGINEER' && !isAdmin) {
          // User is already authenticated in context, so we need to clear auth
          // Use clearAuth instead of logout to avoid navigation while on login page
          await clearAuth();
          setErrorMsg(
            'This account does not have Engineer access. Please use the Client tab to login.'
          );
          return { success: false };
        }

        // Optional: Inform admin users logging in via Client tab
        if (activeTab === 'CLIENT' && isAdmin) {
          setSuccessMsg('Login successful! (Note: You have Admin access)');
        } else {
          setSuccessMsg('Login successful! Redirecting...');
        }

        // Short delay to show success message before redirect
        setTimeout(() => {
          navigate('/dashboard', { replace: true });
        }, 500);
        return { success: true };
      } else {
        // Ensure error message is always a string
        const errorText =
          typeof result.error === 'string' ? result.error : 'Failed to login. Please try again.';
        setErrorMsg(errorText);
        return { success: false };
      }
    } catch (err) {
      console.error('Login error:', err);
      setErrorMsg(typeof err?.message === 'string' ? err.message : 'An unexpected error occurred.');
      return { success: false };
    } finally {
      setLoading(false);
    }
  };

  const handleNavigateToSignUp = () => {
    navigate('/signup');
  };

  const activeColor = activeTab === 'ENGINEER' ? 'indigo' : 'teal';

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
              className={`text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-${activeColor}-200 mb-6 tracking-tight transition-all duration-300`}
            >
              HOMEPOT
            </h1>

            <p className="text-gray-400 mb-4 text-sm font-light">
              {activeTab === 'ENGINEER'
                ? 'Welcome back, Partner. Access your engineering console.'
                : 'Manage your devices and monitor your home.'}
            </p>

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

          <LoginForm
            activeTab={activeTab}
            setActiveTab={handleTabChange}
            email={email}
            setEmail={setEmail}
            password={password}
            setPassword={setPassword}
            loading={loading}
            errorMsg={errorMsg}
            successMsg={successMsg}
            onSubmit={() => handleLogin({ email, password })}
            onNavigateToSignUp={handleNavigateToSignUp}
          />

          <div className="mt-8 text-center space-y-2">
            <p className="text-gray-500 text-xs">Protected by Enterprise Grade Security</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
