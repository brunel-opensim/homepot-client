import { useApp } from '../context/AppContext'

const TABS = [
  { id: 'home', label: 'Home', icon: '⊙' },
  { id: 'permissions', label: 'Perms', icon: '🔒' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
] as const

export default function TabBar() {
  const { currentView, setCurrentView } = useApp()

  return (
    <div className="flex border-t border-slate-700 mt-auto">
      {TABS.map(tab => (
        <button
          key={tab.id}
          onClick={() => setCurrentView(tab.id)}
          className={`flex-1 py-3 flex flex-col items-center gap-0.5 text-xs font-medium transition-colors ${
            currentView === tab.id
              ? 'text-emerald-400 border-t-2 border-emerald-400 -mt-px'
              : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          <span className="text-base">{tab.icon}</span>
          {tab.label}
        </button>
      ))}
    </div>
  )
}
