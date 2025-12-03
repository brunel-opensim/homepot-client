// src/App.jsx
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import AuthProvider from '@/contexts/AuthContext';
import RoutesIndex from './routes';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <RoutesIndex />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
