import { AppProvider, useApp } from './context/AppContext'
import SetupWizard from './views/SetupWizard'
import HomeDashboard from './views/HomeDashboard'
import Permissions from './views/Permissions'
import DeviceInfo from './views/DeviceInfo'
import ClaimDevice from './views/ClaimDevice'

function AppContent() {
  const { currentView } = useApp()

  if (currentView === 'claim') return <ClaimDevice />
  if (currentView === 'setup') return <SetupWizard />
  if (currentView === 'home') return <HomeDashboard />
  if (currentView === 'permissions') return <Permissions />
  if (currentView === 'settings') return <DeviceInfo />

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-400 font-sans">
      <p>Page: {currentView} — coming soon</p>
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  )
}
