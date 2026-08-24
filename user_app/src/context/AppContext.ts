import { createContext, useContext } from 'react'

export interface DeviceInfo {
  deviceId: string
  siteId: string
  deviceName: string
  token: string
}

export interface SetupState {
  siteId: string
  deviceName: string
  deviceType: string
  deviceOs: string
  bootstrapKey: string
  /** Override for the backend URL used by emulator launches (LAN IP for Mac
   *  testing); empty means fall back to the configured apiBaseUrl. */
  backendUrl: string
}

export interface AppContextType {
  deviceInfo: DeviceInfo | null
  setDeviceInfo: (info: DeviceInfo) => void
  isProvisioned: boolean
  setIsProvisioned: (val: boolean) => void
  provisionedChecked: boolean
  setupState: SetupState
  setSetupState: (state: SetupState) => void
  useEmulator: boolean | null
  setUseEmulator: (val: boolean | null) => void
  emulatorType: string
  setEmulatorType: (val: string) => void
  isEmulatorRunning: boolean
  setIsEmulatorRunning: (val: boolean) => void
}

export const AppContext = createContext<AppContextType | null>(null)

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}