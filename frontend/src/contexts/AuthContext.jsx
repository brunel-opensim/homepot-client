import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '@/services/api';
import { AuthContext } from './AuthContextDef';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const handleSessionExpiry = useCallback(
    (opts = {}) => {
      // called when server says 401 or on logout
      setIsAuthenticated(false);
      setUser(null);
      navigate('/login', {
        state: { message: opts.message || 'Session expired. Please login again.' },
        replace: true,
      });
    },
    [navigate]
  );

  // Check session by calling /auth/me (uses httpOnly cookie automatically)
  const checkAuth = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.auth.me();
      if (resp?.success && resp?.data) {
        // Normalize role: If Admin/Engineer privileges exist but role says 'Client', fix display
        let role = resp.data.role;
        if (resp.data.is_admin && (!role || role === 'Client' || role === 'User')) {
          role = 'Admin';
        }

        setUser({
          username: resp.data.username,
          email: resp.data.email,
          isAdmin: resp.data.is_admin,
          fullName: resp.data.full_name,
          role: role,
        });
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch {
      // 401 or network issue -> not authenticated
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();

    // Setup global 401 handler via axios interceptor
    const interceptor = api.raw.interceptors.response.use(
      (r) => r,
      (error) => {
        // Only handle 401 for non-auth endpoints to avoid redirect loops
        const isAuthEndpoint = error?.config?.url?.includes('/auth/');
        if (error?.response?.status === 401 && !isAuthEndpoint) {
          handleSessionExpiry({ message: 'Session expired. Please login again.' });
        }
        return Promise.reject(error);
      }
    );

    return () => {
      api.raw.interceptors.response.eject(interceptor);
    };
  }, [checkAuth, handleSessionExpiry]);

  const login = async (credentials) => {
    try {
      // Server sets httpOnly cookie (XSS protected - not accessible via JS)
      const resp = await api.auth.login(credentials);

      if (resp?.success && resp?.data) {
        // Set user from response data (token is in httpOnly cookie)
        // Normalize role: If Admin/Engineer privileges exist but role says 'Client', fix display
        let role = resp.data.role;
        if (resp.data.is_admin && (!role || role === 'Client' || role === 'User')) {
          role = 'Admin';
        } else if (!role) {
          role = resp.data.is_admin ? 'Admin' : 'User';
        }

        const userData = {
          username: resp.data.username,
          email: resp.data.email,
          isAdmin: resp.data.is_admin,
          fullName: resp.data.full_name,
          role: role,
        };
        setUser(userData);
        setIsAuthenticated(true);

        return { success: true, data: resp };
      }

      return { success: false, error: resp?.message || 'Login failed' };
    } catch (err) {
      // Extract error message safely
      const errorDetail = err?.response?.data?.detail;
      const errorMessage =
        typeof errorDetail === 'string'
          ? errorDetail
          : err?.message || 'Invalid credentials. Please try again.';
      return { success: false, error: errorMessage };
    }
  };

  const signup = async (userData) => {
    try {
      const resp = await api.auth.signup(userData);
      if (resp?.success) {
        return { success: true, data: resp };
      }
      return { success: false, error: resp?.message || 'Signup failed' };
    } catch (err) {
      return { success: false, error: err?.response?.data?.detail || err.message };
    }
  };

  const logout = async () => {
    try {
      await api.auth.logout(); // Server clears the httpOnly cookie
    } catch {
      // ignore logout errors, still clear client state
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      navigate('/login', { replace: true });
    }
  };

  // Clear auth state without navigation (useful when already on login page)
  const clearAuth = async () => {
    try {
      await api.auth.logout();
    } catch {
      // ignore errors
    } finally {
      setUser(null);
      setIsAuthenticated(false);
    }
  };

  const value = { user, isAuthenticated, loading, login, signup, logout, clearAuth, checkAuth };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default AuthProvider;
