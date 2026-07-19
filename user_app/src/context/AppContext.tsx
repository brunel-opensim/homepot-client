import { createContext, useContext, useState } from 'react'
import type { ReactNode } from 'react'

type View = 'setup' | 'home' | 'permissions' | 'settings' | 'claim'

interface DeviceInfo {
  deviceId: string
  siteId: string
  deviceName: string
  token: string
}

interface AppContextType {
  currentView: View
  setCurrentView: (view: View) => void
  deviceInfo: DeviceInfo | null
  setDeviceInfo: (info: DeviceInfo) => void
  isProvisioned: boolean
  setIsProvisioned: (val: boolean) => void
}

const AppContext = createContext<AppContextType | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const provisioned = !!localStorage.getItem('homepot_token')
  const [currentView, setCurrentView] = useState<View>(provisioned ? 'home' : 'setup')
  const [deviceInfo, setDeviceInfo] = useState<DeviceInfo | null>(null)
  const [isProvisioned, setIsProvisioned] = useState(provisioned)

  return (
    <AppContext.Provider value={{
      currentView, setCurrentView,
      deviceInfo, setDeviceInfo,
      isProvisioned, setIsProvisioned,
    }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
