// src/contexts/AuthContext.jsx
import React, { createContext, useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '@/services/api';

// named export - the hook & other modules should import this exact object
export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const logoutTimerRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    console.log('[AuthProvider] mounted');
  }, []);

  const clearTimer = () => {
    if (logoutTimerRef.current) {
      clearTimeout(logoutTimerRef.current);
      logoutTimerRef.current = null;
    }
  };

  const handleSessionExpiry = useCallback(() => {
    console.log('[AuthProvider] session expired, clearing storage');
    clearTimer();
    localStorage.removeItem('auth_token');
    localStorage.removeItem('token_expiry');
    localStorage.removeItem('user_data');
    setIsAuthenticated(false);
    setUser(null);
    navigate('/login', { state: { message: 'Session expired. Please login again.' }, replace: true });
  }, [navigate]);

  const scheduleAutoLogout = (expiryTs) => {
    clearTimer();
    const ms = expiryTs - Date.now();
    if (ms > 0) {
      logoutTimerRef.current = setTimeout(handleSessionExpiry, ms);
    } else {
      handleSessionExpiry();
    }
  };

  const checkAuth = useCallback(() => {
    const token = localStorage.getItem('auth_token');
    const tokenExpiry = localStorage.getItem('token_expiry');
    const userData = localStorage.getItem('user_data');

    if (token && tokenExpiry) {
      const expiry = parseInt(tokenExpiry, 10);
      if (Date.now() < expiry) {
        setIsAuthenticated(true);
        if (userData) {
          try {
            setUser(JSON.parse(userData));
          } catch (e) {
            console.warn('[AuthProvider] failed to parse user_data', e);
          }
        }
        scheduleAutoLogout(expiry);
      } else {
        handleSessionExpiry();
      }
    } else {
      setIsAuthenticated(false);
      setUser(null);
    }
    setLoading(false);
  }, [handleSessionExpiry]);

  useEffect(() => {
    checkAuth();
    return () => clearTimer();
  }, [checkAuth]);

  const login = async (credentials) => {
    // same as your login logic; simplified here for example
    try {
      const response = await api.auth.login(credentials);
      if (response?.success && response.data?.access_token) {
        const { access_token } = response.data;
        localStorage.setItem('auth_token', access_token);

        const expiryDuration = response.data.expires_in ? response.data.expires_in * 1000 : 24 * 60 * 60 * 1000;
        const expiryTime = Date.now() + expiryDuration;
        localStorage.setItem('token_expiry', expiryTime.toString());

        const userData = {
          username: response.data.username || credentials.email,
          role: response.data.role || null,
          email: response.data.email || credentials.email,
        };
        localStorage.setItem('user_data', JSON.stringify(userData));
        setUser(userData);
        setIsAuthenticated(true);
        scheduleAutoLogout(expiryTime);

        return { success: true, data: response.data };
      }
      return { success: false, error: response.message || 'No token' };
    } catch (err) {
      return { success: false, error: err?.response?.data?.message || err.message };
    }
  };

  const logout = () => {
    clearTimer();
    localStorage.removeItem('auth_token');
    localStorage.removeItem('token_expiry');
    localStorage.removeItem('user_data');
    setIsAuthenticated(false);
    setUser(null);
    navigate('/login', { replace: true });
  };

  const value = { user, isAuthenticated, loading, login, logout, checkAuth };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// keep default export for convenience
export default AuthProvider;
