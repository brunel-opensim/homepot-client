import { useState } from 'react'
import TabBar from '../components/TabBar'

interface Permission {
  id: string
  label: string
  description: string
  enabled: boolean
}

const INITIAL_PERMISSIONS: Permission[] = [
  { id: 'root', label: 'Root / Full Access', description: 'Allows full system scan', enabled: true },
  { id: 'process', label: 'Process Monitoring', description: 'View running processes', enabled: true },
  { id: 'filesystem', label: 'File System Access', description: 'Scan files & folders', enabled: false },
  { id: 'network', label: 'Network Monitoring', description: 'Track network connections', enabled: true },
]

function Toggle({ enabled, onChange }: { enabled: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      className={`relative w-12 h-6 rounded-full p-1 transition-colors duration-200 flex-shrink-0 focus:outline-none ${
        enabled ? 'bg-emerald-500' : 'bg-slate-600'
      }`}
    >
      <span className={`block w-4 h-4 bg-white rounded-full shadow-md transition-transform duration-200 ${
        enabled ? 'translate-x-6' : 'translate-x-0'
      }`} />
    </button>
  )
}

export default function Permissions() {
  const [permissions, setPermissions] = useState<Permission[]>(INITIAL_PERMISSIONS)
  const [showWarning, setShowWarning] = useState(false)

  function handleToggle(id: string) {
    const updatedPermissions = permissions.map(p => p.id === id ? { ...p, enabled: !p.enabled } : p)
    setPermissions(updatedPermissions)

    // TODO: Sync to backend immediately to notify Admin Dashboard
    console.log(`Syncing permission ${id} to backend...`)

    setShowWarning(true)
    setTimeout(() => setShowWarning(false), 3000)
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-slate-700">
          <div>
            <h1 className="text-slate-100 font-bold text-base tracking-wide">HOMEPOT Agent</h1>
            <p className="text-slate-500 text-xs">Permissions & Access Control</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center">
            <span className="text-base">🔒</span>
          </div>
        </div>

        {/* Description */}
        <div className="px-5 pt-4">
          <p className="text-slate-400 text-sm">
            Control what the Admin Dashboard can access on this device.
          </p>
        </div>

        {/* Permission Toggles */}
        <div className="px-5 pt-4 flex flex-col gap-0">
          {permissions.map((perm, index) => (
            <div key={perm.id}>
              <div className="flex items-center justify-between py-3.5">
                <div className="flex flex-col gap-0.5 flex-1 mr-4">
                  <span className="text-slate-200 text-sm font-medium">{perm.label}</span>
                  <span className="text-slate-500 text-xs">{perm.description}</span>
                </div>
                <Toggle enabled={perm.enabled} onChange={() => handleToggle(perm.id)} />
              </div>
              {index < permissions.length - 1 && (
                <div className="border-t border-slate-700" />
              )}
            </div>
          ))}
        </div>

        {/* Warning */}
        <div className="px-5 pt-3 pb-5">
          <div className={`w-full rounded-lg px-4 py-2.5 flex items-center gap-2 transition-all duration-300 ${
            showWarning
              ? 'bg-amber-950 border border-amber-800 opacity-100'
              : 'bg-slate-700 border border-slate-600 opacity-60'
          }`}>
            <span className="text-amber-400 text-sm">⚠</span>
            <p className="text-xs text-slate-300">
              {showWarning
                ? 'Syncing changes to Admin Dashboard...'
                : 'Changes apply immediately to the Admin Dashboard.'}
            </p>
          </div>
        </div>

        {/* Tab Bar */}
        <TabBar />
      </div>
    </div>
  )
}
