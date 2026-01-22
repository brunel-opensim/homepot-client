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

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-gray-900/90 backdrop-blur-sm border border-gray-700/50 rounded-lg p-8 shadow-2xl">
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-white mb-6 tracking-wider">HOMEPOT</h1>

            <p className="text-gray-400 mb-4">
              {activeTab === 'ENGINEER'
                ? 'Welcome back, Partner. Access your engineering console.'
                : 'Manage your devices and monitor your home.'}
            </p>

            {sessionMsg && (
              <div className="mb-4 p-3 bg-yellow-900/50 border border-yellow-700 rounded-lg text-yellow-300 text-sm">
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

          <div className="mt-6 text-center">
            <p className="text-gray-400 text-sm">Two-factor authentication required</p>
            <p className="text-gray-400 text-sm">for Engineers</p>
          </div>

          <div className="mt-8 text-center">
            <p className="text-gray-500 text-xs">Powered by HOMEPOT Unified Client</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
