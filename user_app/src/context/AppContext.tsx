import { createContext, useContext, useState } from 'react'
import type { ReactNode } from 'react'

interface DeviceInfo {
  deviceId: string
  siteId: string
  deviceName: string
  token: string
}

interface SetupState {
  siteId: string
  deviceName: string
  deviceType: string
  deviceOs: string
}

interface AppContextType {
  deviceInfo: DeviceInfo | null
  setDeviceInfo: (info: DeviceInfo) => void
  isProvisioned: boolean
  setIsProvisioned: (val: boolean) => void
  setupState: SetupState
  setSetupState: (state: SetupState) => void
}

const AppContext = createContext<AppContextType | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const provisioned = !!localStorage.getItem('homepot_token')
  const [deviceInfo, setDeviceInfo] = useState<DeviceInfo | null>(null)
  const [isProvisioned, setIsProvisioned] = useState(provisioned)
  const [setupState, setSetupState] = useState<SetupState>({
    siteId: '',
    deviceName: '',
    deviceType: 'pos_terminal',
    deviceOs: 'linux',
  })

  return (
    <AppContext.Provider value={{
      deviceInfo, setDeviceInfo,
      isProvisioned, setIsProvisioned,
      setupState, setSetupState,
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
