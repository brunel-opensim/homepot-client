import { AppProvider, useApp } from './context/AppContext'
import SetupWizard from './views/SetupWizard'

function AppContent() {
  const { currentView } = useApp()

  if (currentView === 'setup') return <SetupWizard />

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
