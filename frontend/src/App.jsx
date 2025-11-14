import './App.css';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from '@/contexts/AuthContext';
import ProtectedRoute from '@/components/ProtectedRoute';
import Login from './pages/Login';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import Device from './pages/Device';
import SiteScreen from './pages/Site';
import SiteDeviceScreen from './pages/SiteDevice';
import NotFound from './pages/NotFound';
import Signup from './pages/Signup';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Root route - redirect based on auth status */}
          <Route path="/" element={<Home />} />

          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          {/* Protected routes */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/device"
            element={
              <ProtectedRoute>
                <Device />
              </ProtectedRoute>
            }
          />
          <Route
            path="/site"
            element={
              <ProtectedRoute>
                <SiteScreen />
              </ProtectedRoute>
            }
          />
          <Route
            path="/site/:siteId"
            element={
              <ProtectedRoute>
                <SiteDeviceScreen />
              </ProtectedRoute>
            }
          />
          <Route
            path="/site/:siteId/:deviceId"
            element={
              <ProtectedRoute>
                <Device />
              </ProtectedRoute>
            }
          />

          {/* 404 - Catch all unmatched routes */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
