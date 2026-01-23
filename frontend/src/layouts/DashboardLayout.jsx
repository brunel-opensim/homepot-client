import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function DashboardLayout() {
  const location = useLocation();
  // Check if current path is root OR /dashboard OR /sites (for immersive/full-screen view)
  const isFullScreen =
    location.pathname === '/' ||
    location.pathname === '/dashboard' ||
    location.pathname === '/sites' ||
    location.pathname.startsWith('/sites/') ||
    location.pathname.startsWith('/device') ||
    location.pathname === '/data-collection' ||
    location.pathname === '/useractivity' ||
    location.pathname === '/agents';

  return (
    <div
      className={`w-full ${isFullScreen ? 'fixed inset-0 overflow-hidden bg-white' : 'min-h-screen bg-slate-50'}`}
    >
      <Sidebar />
      <div className={`pl-64 h-full ${isFullScreen ? 'overflow-hidden' : ''}`}>
        <main className={`h-full w-full ${isFullScreen ? 'overflow-hidden p-3' : 'p-8'}`}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
