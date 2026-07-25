import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppProvider, useApp } from './context/AppContext'
import SetupWizard from './views/SetupWizard'
import SignIn from './views/SignIn'
import HomeDashboard from './views/HomeDashboard'
import Permissions from './views/Permissions'
import DeviceInfo from './views/DeviceInfo'
import ClaimDevice from './views/ClaimDevice'

function RootRedirect() {
  const { isProvisioned } = useApp()
  return <Navigate to={isProvisioned ? '/home' : '/setup'} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/setup" element={<SetupWizard />} />
          <Route path="/setup/review" element={<SetupWizard />} />
          <Route path="/signin" element={<SignIn />} />
          <Route path="/home" element={<HomeDashboard />} />
          <Route path="/claim" element={<ClaimDevice />} />
          <Route path="/permissions" element={<Permissions />} />
          <Route path="/settings" element={<DeviceInfo />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppProvider>
    </BrowserRouter>
  )
}
