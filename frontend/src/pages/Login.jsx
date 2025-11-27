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
  const [sessionMsg, setSessionMsg] = useState(null);

  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated } = useAuth();

  // Show session expiry message if redirected from protected route
  useEffect(() => {
    if (location.state?.message) {
      setSessionMsg(location.state.message);
      const timer = setTimeout(() => setSessionMsg(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [location]);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      const from = location.state?.from?.pathname || '/dashboard';
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, location]);

  const handleLogin = async (credentials) => {
    setErrorMsg(null);

    if (!credentials.email || !credentials.password) {
      setErrorMsg('Please provide both email and password.');
      return { success: false };
    }

    setLoading(true);
    try {
      const result = await login(credentials);

      if (result.success) {
        navigate('/dashboard', { replace: true });
        return { success: true };
      } else {
        setErrorMsg(result.error || 'Failed to login. Please try again.');
        return { success: false };
      }
    } catch (err) {
      console.error('Login error:', err);
      setErrorMsg(err?.message || 'An unexpected error occurred.');
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

            {sessionMsg && (
              <div className="mb-4 p-3 bg-yellow-900/50 border border-yellow-700 rounded-lg text-yellow-300 text-sm">
                {sessionMsg}
              </div>
            )}
          </div>

          <LoginForm
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            email={email}
            setEmail={setEmail}
            password={password}
            setPassword={setPassword}
            loading={loading}
            errorMsg={errorMsg}
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
