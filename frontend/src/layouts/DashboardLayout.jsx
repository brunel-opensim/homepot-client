import React from 'react';
import { Outlet } from 'react-router-dom';

export default function DashboardLayout() {
  return (
    <div style={{ minHeight: '100vh' }}>
      <Outlet />
    </div>
  );
}
