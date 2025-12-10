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

const NotFound = lazy(() => import('../pages/NotFound'));

// New Sites Management Pages
const SitesList = lazy(() => import('../pages/Sites/SitesList'));
const SiteForm = lazy(() => import('../pages/Sites/SiteForm'));
const SiteDetail = lazy(() => import('../pages/Sites/SiteDetail'));

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

          {/* New Sites Management Routes */}
          <Route path="sites" element={<SitesList />} />
          <Route path="sites/new" element={<SiteForm />} />
          <Route path="sites/:id" element={<SiteDetail />} />
          <Route path="sites/:id/edit" element={<SiteForm />} />

          {/* If you want / (root after login) to go to /dashboard */}
          <Route index element={<Navigate to="dashboard" replace />} />
        </Route>

        {/* 404 */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
