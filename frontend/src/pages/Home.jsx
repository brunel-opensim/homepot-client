import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

const Home = () => {
  const navigate = useNavigate();
  const { isAuthenticated, loading } = useAuth();

  useEffect(() => {
    if (!loading) {
      if (isAuthenticated) {
        // If user is authenticated, redirect to dashboard
        navigate('/dashboard', { replace: true });
      } else {
        // If user is not authenticated, redirect to login
        navigate('/login', { replace: true });
      }
    }
  }, [isAuthenticated, loading, navigate]);

  // Show loading while checking authentication
  return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-500 mx-auto"></div>
        <p className="text-gray-400 mt-4">Loading...</p>
      </div>
    </div>
  );
};

export default Home;