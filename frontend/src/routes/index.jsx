import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';

// Layouts
import AuthLayout from '../layouts/AuthLayout';
import DashboardLayout from '../layouts/DashboardLayout';

// Pages (reuse your existing pages)
const Home = lazy(() => import('../pages/Home'));
const Login = lazy(() => import('../pages/Login'));
const Signup = lazy(() => import('../pages/Signup'));
const Dashboard = lazy(() => import('../pages/Dashboard'));
const Device = lazy(() => import('../pages/Device'));
const SiteScreen = lazy(() => import('../pages/Site'));
const SiteDeviceScreen = lazy(() => import('../pages/SiteDevice'));
const NotFound = lazy(() => import('../pages/NotFound'));

export default function RoutesIndex() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <Routes>

        {/* Auth routes (login/signup) */}
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
        </Route>

        {/* Protected area - wrapped with ProtectedRoute and DashboardLayout */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }
        >
          {/* When user goes /dashboard => Dashboard page */}
          <Route path="dashboard" element={<Dashboard />} />

          {/* Device & Site routes (protected) */}
          <Route path="device" element={<Device />} />
          <Route path="site" element={<SiteScreen />} />
          <Route path="site/:siteId" element={<SiteDeviceScreen />} />
          <Route path="site/:siteId/:deviceId" element={<Device />} />

          {/* If you want / (root after login) to go to /dashboard */}
          <Route index element={<Navigate to="dashboard" replace />} />
        </Route>

        {/* 404 */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
