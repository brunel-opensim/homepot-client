import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { credentialStorage } from '../services/credentialStorage'
import { verifyDeviceCredentials } from '../services/api'

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
  /** Override for the backend URL used by emulator launches (LAN IP for Mac
   *  testing); empty means fall back to the configured apiBaseUrl. */
  backendUrl: string
}

interface AppContextType {
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

const AppContext = createContext<AppContextType | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [deviceInfo, setDeviceInfo] = useState<DeviceInfo | null>(null)
  const [isProvisioned, setIsProvisioned] = useState(false)
  const [provisionedChecked, setProvisionedChecked] = useState(false)
  const [setupState, setSetupState] = useState<SetupState>(() => {
    // Pre-fill Site ID / Bootstrap Key from scripts/start-userapp.sh args.
    const prefill =
      (window as { electronAPI?: { app?: { prefill?: { siteId?: string; bootstrapKey?: string } } } })
        .electronAPI?.app?.prefill
    return {
      siteId: prefill?.siteId || '',
      deviceName: '',
      deviceType: '',
      deviceOs: 'auto',
      bootstrapKey: prefill?.bootstrapKey || '',
      backendUrl: '',
    }
  })
  const [useEmulator, setUseEmulator] = useState<boolean | null>(null)
  const [emulatorType, setEmulatorType] = useState('linux_pos')
  const [isEmulatorRunning, setIsEmulatorRunning] = useState(false)

  useEffect(() => {
    let mounted = true
    async function checkProvisioned(): Promise<void> {
      const provisioned = await credentialStorage.isProvisioned().catch(() => false)
      let valid = provisioned
      if (provisioned) {
        const [deviceId, apiKey] = await Promise.all([
          credentialStorage.getDeviceId(),
          credentialStorage.getApiKey(),
        ])
        if (deviceId && apiKey) {
          valid = await verifyDeviceCredentials(deviceId, apiKey)
          if (!valid) {
            await credentialStorage.clear().catch(() => {})
          }
        }
      }
      if (mounted) {
        setIsProvisioned(valid)
        setProvisionedChecked(true)
      }
    }
    void checkProvisioned()
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
