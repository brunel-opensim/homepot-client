import { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, shell } from 'electron'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'

const CREDENTIALS_DIR = path.join(os.homedir(), '.homepot')
const CREDENTIALS_FILE = path.join(CREDENTIALS_DIR, 'credentials')
const IDENTITY_FILE = path.join(CREDENTIALS_DIR, 'identity')

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null

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
      preload: path.join(__dirname, 'preload.mjs'),
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

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
