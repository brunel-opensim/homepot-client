import { useLocation, useNavigate } from 'react-router-dom'

const TABS = [
  { id: 'home', label: 'Home', icon: '⊙', path: '/home' },
  { id: 'permissions', label: 'Perms', icon: '🔒', path: '/permissions' },
  { id: 'settings', label: 'Settings', icon: '⚙', path: '/settings' },
] as const

export default function TabBar() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div className="flex border-t border-slate-700 mt-auto">
      {TABS.map(tab => (
        <button
          key={tab.id}
          onClick={() => navigate(tab.path)}
          className={`flex-1 py-3 flex flex-col items-center gap-0.5 text-xs font-medium transition-colors ${
            location.pathname === tab.path
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
