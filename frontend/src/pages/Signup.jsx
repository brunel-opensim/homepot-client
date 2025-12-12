import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import useAuth from '@/hooks/useAuth';
import SignupForm from '@/components/Auth/SignupForm';

const Signup = () => {
  const [activeTab, setActiveTab] = useState('ENGINEER');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [sessionMsg, setSessionMsg] = useState(null);

  const navigate = useNavigate();
  const location = useLocation();
  const { signup, isAuthenticated } = useAuth();

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

  const handleSignUp = async (credentials) => {
    setErrorMsg(null);
    setSuccessMsg(null);

    // basic validation
    if (!credentials.email || !credentials.password || !credentials.name || !credentials.role) {
      setErrorMsg('Please fill in all fields.');
      return { success: false };
    }

    if (credentials.password.length < 6) {
      setErrorMsg('Password must be at least 6 characters long.');
      return { success: false };
    }

    setLoading(true);
    try {
      // Prefer using signup from useAuth if available; otherwise fall back to it failing gracefully.
      let result;
      if (typeof signup === 'function') {
        result = await signup(credentials);
      } else {
        // If your useAuth doesn't provide signup, you can call your API client directly here.
        // Example: import api from '@/services/api' and call api.auth.signup(...)
        // For now, return a not-implemented style result:
        result = {
          success: false,
          error: 'Signup function not available. Please wire up useAuth.signup or call API.',
        };
      }

      if (result.success) {
        setSuccessMsg('Account created! Redirecting to sign in...');
        // show the success briefly then send to login
        setTimeout(() => navigate('/login', { replace: true }), 500);
        return { success: true };
      } else {
        setErrorMsg(result.error || 'Failed to signup. Please try again.');
        return { success: false };
      }
    } catch (err) {
      console.error('Signup error:', err);
      setErrorMsg(err?.message || 'An unexpected error occurred.');
      return { success: false };
    } finally {
      setLoading(false);
    }
  };

  const handleNavigateToSignIn = () => {
    navigate('/login');
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

          <SignupForm
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            name={name}
            setName={setName}
            email={email}
            setEmail={setEmail}
            password={password}
            setPassword={setPassword}
            role={role}
            setRole={setRole}
            loading={loading}
            errorMsg={errorMsg}
            successMsg={successMsg}
            onSubmit={() => handleSignUp({ name, email, password, role, activeTab })}
            onNavigateToSignIn={handleNavigateToSignIn}
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

export default Signup;
