// src/hooks/useAuth.js
import { useContext } from 'react';
import { AuthContext } from '@/contexts/AuthContext';

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    // provide actionable troubleshooting hints
    throw new Error(
      'useAuth must be used within AuthProvider. ' +
        'Make sure AuthProvider from "@/contexts/AuthContext" wraps your app and that imports use the SAME path/casing. ' +
        'Also ensure AuthProvider is rendered inside <BrowserRouter> if it uses useNavigate().'
    );
  }
  return ctx;
}

export default useAuth;
