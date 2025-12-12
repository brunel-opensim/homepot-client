// src/App.jsx
import React, { useEffect } from 'react';
import { BrowserRouter, useLocation } from 'react-router-dom';
import AuthProvider from '@/contexts/AuthContext';
import RoutesIndex from './routes';
import { trackActivity } from './utils/analytics';

// Must be inside BrowserRouter to use useLocation
function PageTracker() {
  const location = useLocation();

  useEffect(() => {
    trackActivity('page_view', location.pathname);
  }, [location.pathname]);

  return null;
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <PageTracker />
        <RoutesIndex />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
