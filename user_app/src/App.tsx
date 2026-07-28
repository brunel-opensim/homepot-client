import { type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppProvider, useApp } from './context/AppContext'
import ErrorBoundary from './components/ErrorBoundary'
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

function Wrapped({ children }: { children: ReactNode }) {
  return <ErrorBoundary>{children}</ErrorBoundary>
}

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <Routes>
          <Route path="/" element={<Wrapped><RootRedirect /></Wrapped>} />
          <Route path="/setup" element={<Wrapped><SetupWizard /></Wrapped>} />
          <Route path="/method" element={<Wrapped><SetupWizard /></Wrapped>} />
          <Route path="/emulator" element={<Wrapped><SetupWizard /></Wrapped>} />
          <Route path="/setup/review" element={<Wrapped><SetupWizard /></Wrapped>} />
          <Route path="/signin" element={<Wrapped><SignIn /></Wrapped>} />
          <Route path="/home" element={<Wrapped><HomeDashboard /></Wrapped>} />
          <Route path="/claim" element={<Wrapped><ClaimDevice /></Wrapped>} />
          <Route path="/permissions" element={<Wrapped><Permissions /></Wrapped>} />
          <Route path="/settings" element={<Wrapped><DeviceInfo /></Wrapped>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppProvider>
    </BrowserRouter>
  )
}
