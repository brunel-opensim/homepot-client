import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { credentialStorage } from '../services/credentialStorage'
import { verifyDeviceCredentials } from '../services/api'
import { AppContext } from './AppContext'
import type { AppContextType, DeviceInfo, SetupState } from './AppContext'

export function AppProvider({ children }: { children: ReactNode }) {
  const [deviceInfo, setDeviceInfo] = useState<DeviceInfo | null>(null)
  const [isProvisioned, setIsProvisioned] = useState(false)
  const [provisionedChecked, setProvisionedChecked] = useState(false)
  const [setupState, setSetupState] = useState<SetupState>(() => {
    // Pre-fill Setup wizard fields from scripts/start-userapp.sh args.
    const prefill =
      (window as {
        electronAPI?: {
          app?: {
            prefill?: {
              siteId?: string
              bootstrapKey?: string
              deviceName?: string
              deviceType?: string
              osDetails?: string
            }
          }
        }
      }).electronAPI?.app?.prefill
    return {
      siteId: prefill?.siteId || '',
      deviceName: prefill?.deviceName || '',
      deviceType: prefill?.deviceType || '',
      deviceOs: prefill?.osDetails || 'auto',
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

  const value: AppContextType = {
    deviceInfo, setDeviceInfo,
    isProvisioned, setIsProvisioned,
    provisionedChecked,
    setupState, setSetupState,
    useEmulator, setUseEmulator,
    emulatorType, setEmulatorType,
    isEmulatorRunning, setIsEmulatorRunning,
  }

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  )
}