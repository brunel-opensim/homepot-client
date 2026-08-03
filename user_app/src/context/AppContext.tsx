import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { credentialStorage } from '../services/credentialStorage'

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
  bootstrapKey: string
}

interface AppContextType {
  deviceInfo: DeviceInfo | null
  setDeviceInfo: (info: DeviceInfo) => void
  isProvisioned: boolean
  setIsProvisioned: (val: boolean) => void
  provisionedChecked: boolean
  setupState: SetupState
  setSetupState: (state: SetupState) => void
  useEmulator: boolean
  setUseEmulator: (val: boolean) => void
  emulatorType: string
  setEmulatorType: (val: string) => void
  isEmulatorRunning: boolean
  setIsEmulatorRunning: (val: boolean) => void
}

const AppContext = createContext<AppContextType | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [deviceInfo, setDeviceInfo] = useState<DeviceInfo | null>(null)
  const [isProvisioned, setIsProvisioned] = useState(false)
  const [provisionedChecked, setProvisionedChecked] = useState(false)
  const [setupState, setSetupState] = useState<SetupState>({
    siteId: '',
    deviceName: '',
    deviceType: 'pos_terminal',
    deviceOs: 'linux',
    bootstrapKey: '',
  })
  const [useEmulator, setUseEmulator] = useState(false)
  const [emulatorType, setEmulatorType] = useState('linux_pos')
  const [isEmulatorRunning, setIsEmulatorRunning] = useState(false)

  useEffect(() => {
    let mounted = true
    credentialStorage
      .isProvisioned()
      .then((provisioned) => {
        if (mounted) {
          setIsProvisioned(provisioned)
          setProvisionedChecked(true)
        }
      })
      .catch(() => {
        if (mounted) setProvisionedChecked(true)
      })
    return () => {
      mounted = false
    }
  }, [])

  return (
    <AppContext.Provider value={{
      deviceInfo, setDeviceInfo,
      isProvisioned, setIsProvisioned,
      provisionedChecked,
      setupState, setSetupState,
      useEmulator, setUseEmulator,
      emulatorType, setEmulatorType,
      isEmulatorRunning, setIsEmulatorRunning,
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
