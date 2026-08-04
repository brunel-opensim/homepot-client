import { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } from 'electron'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import { spawn, type ChildProcess } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

const CREDENTIALS_DIR = path.join(os.homedir(), '.homepot')
const CREDENTIALS_FILE = path.join(CREDENTIALS_DIR, 'credentials')
const IDENTITY_FILE = path.join(CREDENTIALS_DIR, 'identity')
const EMULATOR_DIR = path.join(CREDENTIALS_DIR, 'emulators')

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let emulatorProcess: ChildProcess | null = null
let emulatorDeviceId: string | null = null

function getAssetPath(...segments: string[]): string {
  const dir = __dirname
  if (process.env.VITE_DEV_SERVER_URL) {
    return path.join(process.cwd(), ...segments)
  }
  return path.join(dir, ...segments)
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 420,
    height: 740,
    resizable: false,
    fullscreenable: false,
    title: 'HOMEPOT Agent',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.on('close', (event) => {
    if (tray) {
      event.preventDefault()
      mainWindow?.hide()
    }
  })
}

function createTray() {
  const iconPath = getAssetPath('electron', 'tray-icon.png')
  let icon: Electron.NativeImage
  try {
    icon = nativeImage.createFromPath(iconPath)
  } catch {
    icon = nativeImage.createEmpty()
  }

  tray = new Tray(icon)
  tray.setToolTip('HOMEPOT Agent')

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show',
      click: () => {
        mainWindow?.show()
        mainWindow?.focus()
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        tray?.destroy()
        tray = null
        app.quit()
      },
    },
  ])
  tray.setContextMenu(contextMenu)
  tray.on('click', () => {
    mainWindow?.show()
    mainWindow?.focus()
  })
}

function ensureCredentialsDir(): void {
  if (!fs.existsSync(CREDENTIALS_DIR)) {
    fs.mkdirSync(CREDENTIALS_DIR, { recursive: true, mode: 0o700 })
  }
}

function readCredentialsFile(): Record<string, string> {
  ensureCredentialsDir()
  try {
    if (fs.existsSync(CREDENTIALS_FILE)) {
      const raw = fs.readFileSync(CREDENTIALS_FILE, 'utf-8')
      return JSON.parse(raw)
    }
  } catch {
    // Invalid or unreadable credentials are treated as absent.
  }
  return {}
}

function writeCredentialsFile(data: Record<string, string>): void {
  ensureCredentialsDir()
  fs.writeFileSync(CREDENTIALS_FILE, JSON.stringify(data, null, 2), { mode: 0o600 })
  fs.chmodSync(CREDENTIALS_FILE, 0o600)
}

function getOrCreateDeviceIdentity(): { deviceId: string; machineId: string } {
  ensureCredentialsDir()
  try {
    if (fs.existsSync(IDENTITY_FILE)) {
      const raw = fs.readFileSync(IDENTITY_FILE, 'utf-8')
      return JSON.parse(raw)
    }
  } catch {
    // Invalid or unreadable identity data is replaced below.
  }

  const machineId = os.hostname()
  const deviceId = `device-${crypto.randomUUID()}`
  const identity = { deviceId, machineId }
  fs.writeFileSync(IDENTITY_FILE, JSON.stringify(identity, null, 2), { mode: 0o600 })
  return identity
}

function registerIpcHandlers() {
  ipcMain.handle('credentials:save', (_event, data: Record<string, string>) => {
    writeCredentialsFile(data)
    return true
  })

  ipcMain.handle('credentials:getAll', () => {
    return readCredentialsFile()
  })

  ipcMain.handle('credentials:get', (_event, key: string) => {
    const data = readCredentialsFile()
    return data[key] ?? null
  })

  ipcMain.handle('credentials:clear', () => {
    ensureCredentialsDir()
    try {
      if (fs.existsSync(CREDENTIALS_FILE)) {
        fs.unlinkSync(CREDENTIALS_FILE)
      }
    } catch {
      // Clearing an already unavailable credentials file is idempotent.
    }
    return true
  })

  ipcMain.handle('credentials:isProvisioned', () => {
    const data = readCredentialsFile()
    return !!data.device_id
  })

  ipcMain.handle('device:identity', () => {
    return getOrCreateDeviceIdentity()
  })

  ipcMain.handle('device:dna', () => {
    const interfaces = os.networkInterfaces()
    let mac = '00:00:00:00:00:00'
    let ip = '127.0.0.1'
    for (const iface of Object.values(interfaces)) {
      if (!iface) continue
      for (const addr of iface) {
        if (!addr.internal && addr.family === 'IPv4') {
          mac = addr.mac
          ip = addr.address
          break
        }
      }
      if (mac !== '00:00:00:00:00:00') break
    }
    return {
      hostname: os.hostname(),
      platform: os.platform(),
      release: os.release(),
      mac,
      ip,
    }
  })

  ipcMain.handle('app:getVersion', () => {
    return app.getVersion()
  })

  ipcMain.handle('emulator:start', async (_event, config: {
    emulatorType: string
    backendUrl: string
    siteId: string
    bootstrapKey: string
    deviceName: string
    mockMac?: string
    mockIp?: string
    mockHostname?: string
  }) => {
    if (emulatorProcess) {
      killEmulator()
    }

    const tempConfig = {
      backend_url: config.backendUrl,
      site_id: config.siteId,
      bootstrap_key: config.bootstrapKey,
      device_name: config.deviceName,
      device_type: 'pos_terminal',
      os_details: config.emulatorType === 'android_pos' ? 'Android 14' : 'Linux 6.8.0 (Debian 12)',
      mock_mac: config.mockMac ?? (config.emulatorType === 'android_pos' ? '02:42:ac:11:00:03' : '02:42:ac:11:00:02'),
      mock_ip: config.mockIp ?? '192.168.1.100',
      mock_hostname: config.mockHostname ?? config.deviceName,
      heartbeat_interval_seconds: 10,
      telemetry_interval_seconds: 15,
      command_poll_interval_seconds: 15,
    }

    ensureCredentialsDir()
    if (!fs.existsSync(EMULATOR_DIR)) {
      fs.mkdirSync(EMULATOR_DIR, { recursive: true, mode: 0o700 })
    }

    const configPath = path.join(EMULATOR_DIR, `${config.deviceName}-config.json`)
    fs.writeFileSync(configPath, JSON.stringify(tempConfig, null, 2), { mode: 0o600 })

    const credsPath = path.join(EMULATOR_DIR, `${config.deviceName}.json`)
    if (fs.existsSync(credsPath)) {
      fs.unlinkSync(credsPath)
    }

    const projectRoot = getProjectRoot()
    const emulatorScript = path.join(projectRoot, 'emulators', `${config.emulatorType}_emulator.py`)
    if (!fs.existsSync(emulatorScript)) {
      throw new Error(`Emulator script not found: ${emulatorScript}`)
    }

    const pythonExe = findPython(projectRoot)
    emulatorProcess = spawn(pythonExe, [emulatorScript, '--config', configPath], {
      cwd: projectRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    emulatorProcess.stdout?.on('data', (data: Buffer) => {
      const lines = data.toString().split('\n').filter(Boolean)
      for (const line of lines) {
        console.log(`[emulator] ${line}`)
      }
    })

    emulatorProcess.stderr?.on('data', (data: Buffer) => {
      console.error(`[emulator:err] ${data.toString().trim()}`)
    })

    emulatorProcess.on('exit', (code) => {
      console.log(`[emulator] exited with code ${code}`)
      emulatorProcess = null
      emulatorDeviceId = null
    })

    const creds = await pollForCredentials(credsPath, 30_000)
    if (!creds) {
      killEmulator()
      throw new Error('Emulator did not provision within 30 seconds')
    }

    emulatorDeviceId = creds.device_id
    return { deviceId: creds.device_id, apiKey: creds.api_key }
  })

  ipcMain.handle('emulator:stop', async () => {
    killEmulator()
    return true
  })

  ipcMain.handle('emulator:status', async () => {
    return {
      running: emulatorProcess !== null,
      pid: emulatorProcess?.pid ?? null,
      deviceId: emulatorDeviceId,
    }
  })
}

function killEmulator(): void {
  if (!emulatorProcess) return
  try {
    emulatorProcess.kill('SIGTERM')
    const killed = emulatorProcess.killed
    emulatorProcess = null
    emulatorDeviceId = null
    if (!killed) {
      setTimeout(() => {
        try { emulatorProcess?.kill('SIGKILL') } catch { /* ignore */ }
      }, 3000)
    }
  } catch {
    emulatorProcess = null
    emulatorDeviceId = null
  }
}

function findPython(projectRoot: string): string {
  const candidates = [
    path.join(projectRoot, '.venv', 'bin', 'python3'),
    path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
    'python3',
    'python',
  ]
  for (const candidate of candidates) {
    try {
      fs.accessSync(candidate, fs.constants.X_OK)
      return candidate
    } catch {
      // Try next candidate
    }
  }
  return 'python3'
}

function getProjectRoot(): string {
  let candidate = process.env.VITE_DEV_SERVER_URL
    ? process.cwd()
    : path.dirname(app.getAppPath())

  while (true) {
    if (fs.existsSync(path.join(candidate, 'emulators'))) {
      return candidate
    }
    const parent = path.dirname(candidate)
    if (parent === candidate) {
      return process.env.VITE_DEV_SERVER_URL ? process.cwd() : path.dirname(app.getAppPath())
    }
    candidate = parent
  }
}

function pollForCredentials(credsPath: string, timeoutMs: number): Promise<Record<string, string> | null> {
  return new Promise((resolve) => {
    const start = Date.now()
    const poll = () => {
      if (fs.existsSync(credsPath)) {
        try {
          const data = JSON.parse(fs.readFileSync(credsPath, 'utf-8'))
          if (data.device_id && data.api_key) {
            resolve(data)
            return
          }
        } catch { /* file may still be being written */ }
      }
      if (Date.now() - start >= timeoutMs) {
        resolve(null)
        return
      }
      setTimeout(poll, 500)
    }
    poll()
  })
}

app.whenReady().then(() => {
  registerIpcHandlers()
  createWindow()
  createTray()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('before-quit', () => {
  killEmulator()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
