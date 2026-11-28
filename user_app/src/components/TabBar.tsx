import { useLocation, useNavigate } from 'react-router-dom'
import Icon, { type IconName } from './Icon'

const TABS: { id: string; label: string; icon: IconName; path: string }[] = [
  { id: 'home', label: 'Home', icon: 'home', path: '/home' },
  { id: 'permissions', label: 'Perms', icon: 'lock', path: '/permissions' },
  { id: 'logs', label: 'Logs', icon: 'logs', path: '/logs' },
  { id: 'settings', label: 'Settings', icon: 'settings', path: '/settings' },
]

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
          <span className="text-base">
            <Icon name={tab.icon} />
          </span>
          {tab.label}
        </button>
      ))}
    </div>
  )
}
