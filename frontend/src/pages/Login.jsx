// frontend/src/pages/Login.jsx
import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import useAuth from '@/hooks/useAuth';
import useSessionMessage from '@/hooks/useSessionMessage';
import LoginForm from '@/components/Auth/LoginForm';
import AuthPageLayout from '@/components/Auth/AuthPageLayout';

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
  useSessionMessage(location, setSessionMsg);

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
    <AuthPageLayout
      activeColor={activeColor}
      subtitle={
        activeTab === 'ENGINEER'
          ? 'Welcome back, Partner. Access your engineering console.'
          : 'Manage your devices and monitor your home.'
      }
      sessionMsg={sessionMsg}
      footer={<p className="text-gray-500 text-xs">Protected by Enterprise Grade Security</p>}
    >
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
    </AuthPageLayout>
  );
};

export default Login;
