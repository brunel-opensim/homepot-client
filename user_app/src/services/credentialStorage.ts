/**
 * Credential-storage abstraction for device credentials.
 *
 * The plaintext API key is returned **only** at issuance or rotation.
 * This abstraction ensures the same higher-level workflow works across
 * development simulations and production platforms.
 *
 * Implementations:
 * - `SimulationStorage`  — sessionStorage/localStorage (for dev/testing)
 * - `LinuxFileStorage`   — file on disk with strict permissions (0600)
 * - `WindowsCredManager` — placeholder for Windows Credential Manager / DPAPI
 * - `AndroidKeystore`    — placeholder for Android Keystore
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DeviceCredentials {
  deviceId: string
  apiKey: string
  siteId?: string
  deviceName?: string
  deviceType?: string
  deviceOs?: string
  enrollmentMethod?: string
}

// ---------------------------------------------------------------------------
// Abstract interface
// ---------------------------------------------------------------------------

export interface CredentialStorage {
  /** Persist credentials after a successful provision or claim. */
  save(creds: DeviceCredentials): Promise<void>

  /** Retrieve the stored API key.  Returns ``null`` if not provisioned. */
  getApiKey(): Promise<string | null>

  /** Retrieve the stored device ID.  Returns ``null`` if not provisioned. */
  getDeviceId(): Promise<string | null>

  /** Retrieve a metadata field by key. */
  getMetadata(key: string): Promise<string | null>

  /** Remove all stored credentials (unpair / factory-reset). */
  clear(): Promise<void>

  /** ``true`` if credentials are present (device is provisioned). */
  isProvisioned(): Promise<boolean>
}

// ---------------------------------------------------------------------------
// Simulation storage (sessionStorage + localStorage)
// ---------------------------------------------------------------------------

const LS_PREFIX = 'homepot_'
const SS_API_KEY = 'homepot_api_key'

function lsKey(key: string): string {
  return `${LS_PREFIX}${key}`
}

export class SimulationStorage implements CredentialStorage {
  async save(creds: DeviceCredentials): Promise<void> {
    localStorage.setItem(lsKey('device_id'), creds.deviceId)
    localStorage.setItem(lsKey('device_name'), creds.deviceName ?? '')
    localStorage.setItem(lsKey('device_type'), creds.deviceType ?? '')
    localStorage.setItem(lsKey('device_os'), creds.deviceOs ?? '')
    localStorage.setItem(lsKey('enrollment_method'), creds.enrollmentMethod ?? 'self-enrolled')
    if (creds.siteId) {
      localStorage.setItem(lsKey('site_id'), creds.siteId)
    }
    // API key goes to sessionStorage (cleared when tab closes)
    sessionStorage.setItem(SS_API_KEY, creds.apiKey)
  }

  async getApiKey(): Promise<string | null> {
    return sessionStorage.getItem(SS_API_KEY)
  }

  async getDeviceId(): Promise<string | null> {
    return localStorage.getItem(lsKey('device_id'))
  }

  async getMetadata(key: string): Promise<string | null> {
    return localStorage.getItem(lsKey(key))
  }

  async clear(): Promise<void> {
    const keysToRemove: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (k?.startsWith(LS_PREFIX)) keysToRemove.push(k)
    }
    keysToRemove.forEach((k) => localStorage.removeItem(k))
    sessionStorage.removeItem(SS_API_KEY)
  }

  async isProvisioned(): Promise<boolean> {
    return localStorage.getItem(lsKey('device_id')) !== null
  }
}

// ---------------------------------------------------------------------------
// Linux file storage (file on disk with strict permissions)
// ---------------------------------------------------------------------------

/**
 * LinuxFileStorage stores credentials in a JSON file at ``~/.homepot/credentials``
 * with ``0600`` permissions.  Falls back to ``SimulationStorage`` if the
 * filesystem API is unavailable (browser environment).
 */
export class LinuxFileStorage implements CredentialStorage {
  private fallback: SimulationStorage
  private filePath = ''

  constructor() {
    this.fallback = new SimulationStorage()
    // Attempt to resolve a writable path (only in Node/Electron/Tauri)
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const os = require('os') as { homedir(): string }
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const path = require('path') as { join(...parts: string[]): string }
      this.filePath = path.join(os.homedir(), '.homepot', 'credentials')
    } catch {
      // Browser environment — use simulation storage
    }
  }

  private async readFile(): Promise<Record<string, string> | null> {
    if (!this.filePath) return null
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const fs = require('fs') as {
        existsSync(p: string): boolean
        readFileSync(p: string, enc: string): string
        mkdirSync(p: string, opts: { recursive: boolean }): void
        writeFileSync(p: string, data: string, opts: { mode: number }): void
        chmodSync(p: string, mode: number): void
      }
      if (!fs.existsSync(this.filePath)) return null
      const raw = fs.readFileSync(this.filePath, 'utf-8')
      return JSON.parse(raw) as Record<string, string>
    } catch {
      return null
    }
  }

  private async writeFile(data: Record<string, string>): Promise<void> {
    if (!this.filePath) return
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const fs = require('fs') as {
        existsSync(p: string): boolean
        mkdirSync(p: string, opts: { recursive: boolean }): void
        writeFileSync(p: string, data: string, opts: { mode: number }): void
        chmodSync(p: string, mode: number): void
      }
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const path = require('path') as { dirname(p: string): string }
      const dir = path.dirname(this.filePath)
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true })
      }
      fs.writeFileSync(this.filePath, JSON.stringify(data, null, 2), { mode: 0o600 })
      fs.chmodSync(this.filePath, 0o600)
    } catch {
      // Fallback to simulation storage
      await this.fallback.clear()
    }
  }

  async save(creds: DeviceCredentials): Promise<void> {
    if (this.filePath) {
      const data: Record<string, string> = {
        device_id: creds.deviceId,
        api_key: creds.apiKey,
      }
      if (creds.siteId) data.site_id = creds.siteId
      if (creds.deviceName) data.device_name = creds.deviceName
      if (creds.deviceType) data.device_type = creds.deviceType
      if (creds.deviceOs) data.device_os = creds.deviceOs
      if (creds.enrollmentMethod) data.enrollment_method = creds.enrollmentMethod
      await this.writeFile(data)
    }
    // Also save to simulation storage for backward compat
    await this.fallback.save(creds)
  }

  async getApiKey(): Promise<string | null> {
    if (this.filePath) {
      const data = await this.readFile()
      if (data?.api_key) return data.api_key
    }
    return this.fallback.getApiKey()
  }

  async getDeviceId(): Promise<string | null> {
    if (this.filePath) {
      const data = await this.readFile()
      if (data?.device_id) return data.device_id
    }
    return this.fallback.getDeviceId()
  }

  async getMetadata(key: string): Promise<string | null> {
    if (this.filePath) {
      const data = await this.readFile()
      if (data?.[key]) return data[key]
    }
    return this.fallback.getMetadata(key)
  }

  async clear(): Promise<void> {
    if (this.filePath) {
      try {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const fs = require('fs') as { unlinkSync(p: string): void }
        if (fs.existsSync(this.filePath)) {
          fs.unlinkSync(this.filePath)
        }
      } catch {
        // ignore
      }
    }
    await this.fallback.clear()
  }

  async isProvisioned(): Promise<boolean> {
    if (this.filePath) {
      const data = await this.readFile()
      if (data?.device_id) return true
    }
    return this.fallback.isProvisioned()
  }
}

// ---------------------------------------------------------------------------
// Platform-aware factory
// ---------------------------------------------------------------------------

/**
 * Returns the appropriate ``CredentialStorage`` implementation for the
 * current platform.
 *
 * - **Linux** (Node/Electron/Tauri) → ``LinuxFileStorage``
 * - **Browser** → ``SimulationStorage``
 * - **Windows** → ``WindowsCredManager`` *(placeholder, falls back to simulation)*
 * - **Android** → ``AndroidKeystore`` *(placeholder, falls back to simulation)*
 */
export function createCredentialStorage(): CredentialStorage {
  // In a browser context (no `process` or `require`), use simulation
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    // Check for Android bridge
    if (navigator.userAgent?.toLowerCase().includes('android')) {
      // AndroidKeystore placeholder — uses simulation for now
      console.warn('[credentialStorage] Android Keystore not yet implemented; using SimulationStorage')
      return new SimulationStorage()
    }
    return new SimulationStorage()
  }

  // Server-side / Electron / Tauri — detect platform
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const os = require('os') as { platform(): string }
    const platform = os.platform()
    if (platform === 'linux') {
      return new LinuxFileStorage()
    }
    if (platform === 'win32') {
      console.warn('[credentialStorage] Windows Credential Manager not yet implemented; using LinuxFileStorage')
      return new LinuxFileStorage()
    }
  } catch {
    // Fallback
  }

  return new SimulationStorage()
}

// ---------------------------------------------------------------------------
// Singleton instance
// ---------------------------------------------------------------------------

/** Application-wide credential storage instance. */
export const credentialStorage: CredentialStorage = createCredentialStorage()
