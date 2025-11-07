import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '@/services/api';
import { AuthContext } from './auth-context';

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const navigate = useNavigate();

  const handleSessionExpiry = useCallback(() => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('token_expiry');
    localStorage.removeItem('user_data');
    setIsAuthenticated(false);
    setUser(null);
    navigate('/login', { state: { message: 'Session expired. Please login again.' } });
  }, [navigate]);

  const checkAuth = useCallback(() => {
    const token = localStorage.getItem('auth_token');
    const tokenExpiry = localStorage.getItem('token_expiry');
    const userData = localStorage.getItem('user_data');
    
    if (token && tokenExpiry) {
      const expiryTime = parseInt(tokenExpiry, 10);
      const now = Date.now();
      
      if (now < expiryTime) {
        setIsAuthenticated(true);
        if (userData) {
          try {
            setUser(JSON.parse(userData));
          } catch (e) {
            console.error('Failed to parse user data:', e);
          }
        }
        const timeUntilExpiry = expiryTime - now;
        setTimeout(() => handleSessionExpiry(), timeUntilExpiry);
      } else {
        handleSessionExpiry();
      }
    } else {
      setIsAuthenticated(false);
    }
    setLoading(false);
  }, [handleSessionExpiry]);

  // Check if token exists and is valid on mount
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = async (credentials) => {
    try {
      const response = await api.auth.login(credentials);
      
      // Handle the nested response structure: response.data.access_token
      if (response.success && response.data?.access_token) {
        const { access_token, username, role } = response.data;
        
        // Store token
        localStorage.setItem('auth_token', access_token);
        
        // Calculate expiry time (default 24 hours if not provided)
        const expiryDuration = response.data.expires_in 
          ? response.data.expires_in * 1000 
          : 24 * 60 * 60 * 1000; // 24 hours
        const expiryTime = Date.now() + expiryDuration;
        localStorage.setItem('token_expiry', expiryTime.toString());
        
        // Store user data
        const userData = {
          username,
          role,
          email: credentials.email
        };
        localStorage.setItem('user_data', JSON.stringify(userData));
        setUser(userData);
        
        setIsAuthenticated(true);
        
        // Set up auto-logout timer
        setTimeout(() => {
          handleSessionExpiry();
        }, expiryDuration);
        
        return { success: true, data: response.data };
      }
      
      return { 
        success: false, 
        error: response.message || 'No token received' 
      };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.message || error.response?.data?.detail || error.message 
      };
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('token_expiry');
    localStorage.removeItem('user_data');
    setIsAuthenticated(false);
    setUser(null);
    navigate('/login');
  };

  const value = {
    user,
    isAuthenticated,
    loading,
    login,
    logout,
    checkAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};