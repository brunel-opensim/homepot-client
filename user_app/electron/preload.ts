import { contextBridge, ipcRenderer } from 'electron'

// Pre-fill values passed by scripts/start-userapp.sh via env (--site-id and
// --bootstrap-key). Exposed synchronously so the Setup wizard can initialise
// its fields without a race.
const prefill = {
  siteId: process.env.HOMEPOT_PREFILL_SITE_ID || '',
  bootstrapKey: process.env.HOMEPOT_PREFILL_BOOTSTRAP_KEY || '',
}

contextBridge.exposeInMainWorld('electronAPI', {
  credentials: {
    save: (data: Record<string, string>) => ipcRenderer.invoke('credentials:save', data),
    getAll: () => ipcRenderer.invoke('credentials:getAll'),
    get: (key: string) => ipcRenderer.invoke('credentials:get', key),
    clear: () => ipcRenderer.invoke('credentials:clear'),
    isProvisioned: () => ipcRenderer.invoke('credentials:isProvisioned'),
  },
  device: {
    identity: () => ipcRenderer.invoke('device:identity'),
    dna: () => ipcRenderer.invoke('device:dna'),
  },
  app: {
    getVersion: () => ipcRenderer.invoke('app:getVersion'),
    getRecentLogs: (limit = 15) => ipcRenderer.invoke('app:getRecentLogs', limit),
    prefill,
  },
  emulator: {
    start: (config: {
      emulatorType: string
      backendUrl: string
      siteId: string
      bootstrapKey: string
      deviceName: string
      mockMac?: string
      mockIp?: string
      mockHostname?: string
    }) => ipcRenderer.invoke('emulator:start', config),
    stop: () => ipcRenderer.invoke('emulator:stop'),
    status: () => ipcRenderer.invoke('emulator:status'),
  },
})
