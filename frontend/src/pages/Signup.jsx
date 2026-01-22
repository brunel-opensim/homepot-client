import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import useAuth from '@/hooks/useAuth';
import SignupForm from '@/components/Auth/SignupForm';

const Signup = () => {
  const [activeTab, setActiveTab] = useState('ENGINEER');
  const [name, setName] = useState('');
  const [username, setUsername] = useState('');
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

  // Smart Role Selection: Update role based on active tab
  useEffect(() => {
    if (activeTab === 'ENGINEER') {
      setRole('Engineer'); // Engineer tab -> Engineer role
    } else {
      setRole('Client'); // Client tab -> Client role
    }
  }, [activeTab]);

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

    // Strict validation including username for consistency
    if (
      !credentials.email ||
      !credentials.password ||
      !credentials.full_name ||
      !credentials.username ||
      !credentials.role
    ) {
      setErrorMsg('Please fill in all fields including Username.');
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
        result = {
          success: false,
          error: 'Signup function not available. Please wire up useAuth.signup or call API.',
        };
      }

      if (result.success) {
        setSuccessMsg('Account created! Redirecting to sign in...');
        setTimeout(() => navigate('/login', { replace: true }), 1000);
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
              className={`text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-${activeColor}-200 mb-6 tracking-tight transition-all duration-300`}
            >
              HOMEPOT
            </h1>

            <p className="text-gray-400 mb-4 text-sm font-light">
              {activeTab === 'ENGINEER'
                ? 'Join as a Partner. Build the future of home automation.'
                : 'Create your account to start managing your smart home.'}
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

          <SignupForm
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            name={name}
            setName={setName}
            username={username}
            setUsername={setUsername}
            email={email}
            setEmail={setEmail}
            password={password}
            setPassword={setPassword}
            loading={loading}
            errorMsg={errorMsg}
            successMsg={successMsg}
            onSubmit={() => handleSignUp({ full_name: name, username, email, password, role })}
            onNavigateToSignIn={handleNavigateToSignIn}
          />

          <div className="mt-8 text-center space-y-2">
            <p className="text-gray-500 text-xs">
              By signing up, you agree to our Terms of Service
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Signup;
