import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import useAuth from '@/hooks/useAuth';
import useSessionMessage from '@/hooks/useSessionMessage';
import SignupForm from '@/components/Auth/SignupForm';
import AuthPageLayout from '@/components/Auth/AuthPageLayout';

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
  useSessionMessage(location, setSessionMsg);

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
    <AuthPageLayout
      activeColor={activeColor}
      headingClassName="text-4xl"
      subtitle={
        activeTab === 'ENGINEER'
          ? 'Join as a Partner. Build the future of home automation.'
          : 'Create your account to start managing your smart home.'
      }
      sessionMsg={sessionMsg}
      footer={
        <p className="text-gray-500 text-xs">By signing up, you agree to our Terms of Service</p>
      }
    >
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
    </AuthPageLayout>
  );
};

export default Signup;
