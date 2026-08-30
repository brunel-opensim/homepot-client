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
const AGENT_DIR = path.join(CREDENTIALS_DIR, 'agent')
const AGENT_CONFIG_FILE = path.join(AGENT_DIR, 'agent-config.json')
const MAX_APP_LOG_ENTRIES = 15
const hasSingleInstanceLock = app.requestSingleInstanceLock()

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let emulatorProcess: ChildProcess | null = null
let emulatorDeviceId: string | null = null
let agentProcess: ChildProcess | null = null
// Recent stderr lines from the emulator process, surfaced in the setup error
// when the emulator fails to start (e.g. missing python/httpx).
let emulatorStderr: string[] = []

interface EmulatorFileConfig {
  emulator_type?: string
  device_name?: string
  os_details?: string
}

interface EmulatorProfile {
  emulator_type: string
  os_details: string
  device_type: string
  mock_mac: string
}

const EMULATOR_PROFILES: Record<string, EmulatorProfile> = {
  linux_pos: { emulator_type: 'linux_pos', os_details: 'Linux 6.8.0 (Debian 12)', device_type: 'pos_terminal', mock_mac: '02:42:ac:11:00:02' },
  android_pos: { emulator_type: 'android_pos', os_details: 'Android 14', device_type: 'pos_terminal', mock_mac: '02:42:ac:11:00:03' },
  windows_pos: { emulator_type: 'windows_pos', os_details: 'Windows 11', device_type: 'pos_terminal', mock_mac: '02:42:ac:11:00:04' },
  macos_pos: { emulator_type: 'macos_pos', os_details: 'macOS 14', device_type: 'pos_terminal', mock_mac: '02:42:ac:11:00:05' },
  ios_pos: { emulator_type: 'ios_pos', os_details: 'iOS 17', device_type: 'tablet', mock_mac: '02:42:ac:11:00:06' },
}

function emulatorProfile(emulatorType: string): EmulatorProfile {
  return EMULATOR_PROFILES[emulatorType] ?? EMULATOR_PROFILES.linux_pos
}

function inferEmulatorType(osDetails?: string): string {
  const value = (osDetails ?? '').toLowerCase()
  if (value.includes('android')) return 'android_pos'
  if (value.includes('windows')) return 'windows_pos'
  if (value.includes('mac')) return 'macos_pos'
  if (value.includes('ios')) return 'ios_pos'
  return 'linux_pos'
}

interface AppLogEntry {
  id: string
  timestamp: string
  level: 'info' | 'warning' | 'error'
  category: string
  message: string
}

function getAppLogFile(): string {
  return path.join(app.getPath('userData'), 'app-events.json')
}

function readAppLog(): AppLogEntry[] {
  try {
    const data = JSON.parse(fs.readFileSync(getAppLogFile(), 'utf-8'))
    return Array.isArray(data) ? data.slice(-MAX_APP_LOG_ENTRIES) : []
  } catch {
    return []
  }
}

function recordAppEvent(level: AppLogEntry['level'], category: string, message: string): void {
  try {
    const logFile = getAppLogFile()
    fs.mkdirSync(path.dirname(logFile), { recursive: true, mode: 0o700 })
    const entries = [
      ...readAppLog(),
      {
        id: crypto.randomUUID(),
        timestamp: new Date().toISOString(),
        level,
        category,
        message,
      },
    ].slice(-MAX_APP_LOG_ENTRIES)
    fs.writeFileSync(logFile, JSON.stringify(entries, null, 2), { mode: 0o600 })
    fs.chmodSync(logFile, 0o600)
  } catch (error) {
    console.error('[app-log] Failed to write event:', error)
  }
}

if (!hasSingleInstanceLock) {
  app.quit()
}

app.on('second-instance', () => {
  recordAppEvent('warning', 'application', 'Another launch was redirected to the running application')
  mainWindow?.show()
  mainWindow?.focus()
})

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

  mainWindow.webContents.on('did-finish-load', () => {
    recordAppEvent('info', 'application', 'User interface ready')
  })
  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    recordAppEvent('error', 'application', `User interface stopped unexpectedly (${details.reason})`)
  })

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

/**
 * Adopt an already-provisioned emulator device so a plain launch bypasses the
 * Setup wizard and lands on Home.
 *
 * When a device is created outside this app (e.g. via scripts/start-emulator.sh),
 * its credentials live only in the emulator stash (~/.homepot/emulators/<name>.json,
 * written by pos_engine.py). With no ~/.homepot/credentials file the app would
 * otherwise boot into Setup despite a device existing on the Dashboard. If a
 * credentials file is absent and a valid emulator credential file is present,
 * promote the most recently written one into the app credentials so routing
 * treats the app as provisioned.
 */
function adoptExistingEmulatorDevice(): void {
  if (Object.keys(readCredentialsFile()).length > 0) return

  ensureCredentialsDir()
  if (!fs.existsSync(EMULATOR_DIR)) return

  let candidates: string | null = null
  let bestMtime = -1
  for (const entry of fs.readdirSync(EMULATOR_DIR)) {
    // Emulator credential files are <device>.json (device_id + api_key);
    // skip the <device>-config.json files written by emulator:start.
    if (!entry.endsWith('.json') || entry.endsWith('-config.json')) continue
    const filePath = path.join(EMULATOR_DIR, entry)
    const stat = fs.statSync(filePath)
    if (stat.isDirectory()) continue
    if (stat.mtimeMs > bestMtime) {
      bestMtime = stat.mtimeMs
      candidates = filePath
    }
  }
  if (!candidates) return

  try {
    const emulatorCreds = JSON.parse(fs.readFileSync(candidates, 'utf-8')) as Record<string, string>
    if (!emulatorCreds.device_id || !emulatorCreds.api_key) return
    writeCredentialsFile({
      device_id: emulatorCreds.device_id,
      api_key: emulatorCreds.api_key,
      device_name: emulatorCreds.device_name ?? '',
      device_type: emulatorCreds.device_type ?? 'pos_terminal',
      device_os: emulatorCreds.os_details ?? '',
      site_id: emulatorCreds.site_id ?? '',
      enrollment_method: 'emulated',
    })
    console.log(`[emulator] Adopted persisted device ${emulatorCreds.device_name ?? emulatorCreds.device_id}`)
    recordAppEvent('info', 'setup', `Adopted existing emulated device (${emulatorCreds.device_name ?? emulatorCreds.device_id})`)
  } catch (error) {
    console.error('[emulator] Failed to adopt persisted device:', error)
  }
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
    recordAppEvent('info', 'setup', 'Device setup completed successfully')
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

  ipcMain.handle('app:getRecentLogs', (_event, requestedLimit = MAX_APP_LOG_ENTRIES) => {
    const limit = Math.max(1, Math.min(MAX_APP_LOG_ENTRIES, Number(requestedLimit) || MAX_APP_LOG_ENTRIES))
    return readAppLog().slice(-limit).reverse()
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
    recordAppEvent('info', 'emulator', `Starting ${config.emulatorType} device emulator`)
    if (emulatorProcess) {
      killEmulator()
    }

    const profile = emulatorProfile(config.emulatorType)

    const tempConfig = {
      emulator_type: config.emulatorType,
      backend_url: config.backendUrl,
      site_id: config.siteId,
      bootstrap_key: config.bootstrapKey,
      device_name: config.deviceName,
      device_type: profile.device_type,
      os_details: profile.os_details,
      mock_mac: config.mockMac ?? profile.mock_mac,
      mock_ip: config.mockIp ?? '192.168.1.100',
      mock_hostname: config.mockHostname ?? config.deviceName,
      heartbeat_interval_seconds: 10,
      telemetry_interval_seconds: 15,
      command_poll_interval_seconds: 15,
      // The app's device experience should not randomly simulate command/push
      // failures (the failure rate is a standalone start-emulator.sh testing
      // knob); the wake-up must fire reliably so commands are pulled instantly.
      command_failure_rate: 0,
      // Poll the pending-push queue frequently so a command wake-up is
      // discovered quickly (near-instant pull) instead of the default 15s.
      push_poll_interval_seconds: 2,
      permission_consent_mode: 'external',
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

    try {
      startEmulatorProcess(config.emulatorType, configPath)
    } catch (error) {
      recordAppEvent('error', 'emulator', `Device emulator failed to start: ${error instanceof Error ? error.message : 'unknown error'}`)
      throw error
    }

    const creds = await pollForCredentials(credsPath, 30_000)
    if (!creds) {
      killEmulator()
      const stderr = emulatorStderr.join('\n')
      recordAppEvent('error', 'setup', 'Device emulator setup timed out')
      const detail = stderr
        ? ` Emulator output: ${stderr.slice(0, 500)}`
        : ' The emulator did not provision within 30 seconds.'
      throw new Error(`Device emulator failed to start.${detail}`)
    }

    emulatorDeviceId = creds.device_id
    recordAppEvent('info', 'emulator', 'Device emulator started successfully')
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

  ipcMain.handle('agent:start', async () => {
    recordAppEvent('info', 'agent', 'Starting on-device agent')
    const started = startAgentProcess()
    return { started }
  })

  ipcMain.handle('agent:status', async () => {
    return {
      running: agentProcess !== null,
      pid: agentProcess?.pid ?? null,
    }
  })

  ipcMain.handle('agent:stop', async () => {
    killAgent()
    return true
  })
}

// --- On-device agent (real command execution) -------------------------------

/**
 * The self-contained User App runs the bundled Python device agent
 * (`homepot.agent.real_device_agent`) as a background child process. The agent
 * registers with the backend, streams telemetry/heartbeats, polls pending
 * commands, executes them against the host OS via `command_poller.process_command`,
 * and reports results — the same runtime the emulators simulate.
 *
 * Credential handoff: the agent's `create_credential_storage()` reads
 * `~/.homepot/credentials` (the same file Electron writes), and we also write an
 * explicit config file so `device_id`/`api_key`/`backend_url` are always present.
 */
function resolveBackendUrl(credentials: Record<string, string>): string {
  if (process.env.HOMEPOT_BACKEND_URL) return process.env.HOMEPOT_BACKEND_URL
  if (credentials.backend_url) return credentials.backend_url
  return 'http://localhost:8000/api/v1'
}

function writeAgentConfig(): string | null {
  const credentials = readCredentialsFile()
  const deviceId = credentials.device_id
  const apiKey = credentials.api_key
  if (!deviceId || !apiKey) return null

  const config = {
    backend_url: resolveBackendUrl(credentials),
    device_id: deviceId,
    api_key: apiKey,
    site_id: credentials.site_id ?? '',
    device_name: credentials.device_name ?? '',
    device_type: credentials.device_type ?? 'pos_terminal',
    os_details: credentials.device_os ?? os.platform(),
    heartbeat_interval_seconds: 30,
    telemetry_interval_seconds: 30,
    command_poll_interval_seconds: 15,
    retry_flush_interval_seconds: 60,
    ipc_enabled: false,
    watchdog_enabled: true,
    watchdog_interval_seconds: 10,
    shutdown_timeout_seconds: 30,
    log_level: 'INFO',
  }

  ensureCredentialsDir()
  if (!fs.existsSync(AGENT_DIR)) {
    fs.mkdirSync(AGENT_DIR, { recursive: true, mode: 0o700 })
  }
  fs.writeFileSync(AGENT_CONFIG_FILE, JSON.stringify(config, null, 2), { mode: 0o600 })
  return AGENT_CONFIG_FILE
}

function startAgentProcess(): boolean {
  const configPath = writeAgentConfig()
  if (!configPath) return false
  if (agentProcess) return true

  const credentials = readCredentialsFile()
  const deviceSlug = credentials.device_name || credentials.device_id || 'agent'
  const logFile = deviceLogFile(deviceSlug, 'agent')

  const projectRoot = getProjectRoot()
  const pythonExe = findPython(projectRoot)
  const child = spawn(pythonExe, ['-u', '-m', 'homepot.agent.real_device_agent'], {
    cwd: projectRoot,
    env: {
      ...process.env,
      PYTHONPATH: path.join(projectRoot, 'backend', 'src'),
      HOMEPOT_AGENT_CONFIG: configPath,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  agentProcess = child

  child.stdout?.on('data', (data: Buffer) => {
    for (const line of data.toString().split('\n').filter(Boolean)) {
      console.log(`[agent] ${line}`)
      appendDeviceLog(logFile, 'agent', line)
    }
  })
  child.stderr?.on('data', (data: Buffer) => {
    for (const line of data.toString().split('\n').filter(Boolean)) {
      console.error(`[agent:err] ${line}`)
      appendDeviceLog(logFile, 'agent:err', line)
    }
  })
  child.on('error', (error) => {
    recordAppEvent('error', 'agent', `Device agent process error: ${error.message}`)
  })
  child.on('exit', (code) => {
    console.log(`[agent] exited with code ${code}`)
    recordAppEvent(code === 0 ? 'info' : 'error', 'agent', `Device agent exited with code ${code ?? 'unknown'}`)
    if (agentProcess === child) {
      agentProcess = null
    }
  })

  recordAppEvent('info', 'agent', 'Device agent started')
  return true
}

function killAgent(): void {
  if (!agentProcess) return
  recordAppEvent('info', 'agent', 'Stopping device agent')
  const processToKill = agentProcess
  try {
    processToKill.kill('SIGTERM')
    agentProcess = null
  } catch {
    agentProcess = null
  }
}

function startDeviceAgentIfProvisioned(): void {
  const credentials = readCredentialsFile()
  if (!credentials.device_id || !credentials.api_key) return
  // Emulated devices keep using the emulator process instead.
  if (credentials.enrollment_method === 'emulated') return
  startAgentProcess()
}

function killEmulator(): void {
  if (!emulatorProcess) return
  recordAppEvent('info', 'emulator', 'Stopping device emulator')
  const processToKill = emulatorProcess
  try {
    processToKill.kill('SIGTERM')
    const killed = processToKill.killed
    emulatorProcess = null
    emulatorDeviceId = null
    if (!killed) {
      setTimeout(() => {
        try { processToKill.kill('SIGKILL') } catch { /* ignore */ }
      }, 3000)
    }
  } catch {
    emulatorProcess = null
    emulatorDeviceId = null
  }
}

/**
 * Persist device (emulator/agent) stdout+stderr to a dedicated file under the
 * repo's `logs/` dir so live output (telemetry, commands, wake-ups) is
 * available on disk regardless of where Electron's console goes. Falls back
 * silently when the logs dir isn't writable (e.g. packaged apps).
 */
/**
 * Resolve a per-device log file under the repo's `logs/` dir, mirroring the
 * standalone launcher convention (`logs/emulator-<instance>.log`).
 */
function deviceLogFile(slug: string, kind: 'emulator' | 'agent'): string {
  const safeSlug = slug.replace(/[\\/]/g, '_')
  const logsDir = path.join(getProjectRoot(), 'logs')
  fs.mkdirSync(logsDir, { recursive: true })
  const logFile = path.join(logsDir, `${kind}-${safeSlug}.log`)
  try {
    // Seed the file eagerly so it exists the moment the process starts, even
    // before the first output line arrives.
    if (!fs.existsSync(logFile)) {
      fs.writeFileSync(
        logFile,
        `[${new Date().toISOString()}] [${kind}] ${kind} log for '${safeSlug}' created\n`,
      )
    }
  } catch {
    // Log file is best-effort; never break the app because of it.
  }
  return logFile
}

/**
 * Persist device (emulator/agent) stdout+stderr to a per-device file so live
 * output (telemetry, commands, wake-ups) is available on disk regardless of
 * where Electron's console goes. Falls back silently when not writable.
 */
function appendDeviceLog(logFile: string, tag: string, line: string): void {
  try {
    fs.appendFileSync(logFile, `[${new Date().toISOString()}] [${tag}] ${line}\n`)
  } catch {
    // Log file is best-effort; never break the app because of it.
  }
}

function startEmulatorProcess(emulatorType: string, configPath: string): void {
  const projectRoot = getProjectRoot()
  const emulatorScript = path.join(projectRoot, 'emulators', `${emulatorType}_emulator.py`)
  if (!fs.existsSync(emulatorScript)) {
    throw new Error(`Emulator script not found: ${emulatorScript}`)
  }

  const pythonExe = findPython(projectRoot)
  emulatorStderr = []
  const deviceSlug = path.basename(configPath).replace(/-config\.json$/, '')
  const logFile = deviceLogFile(deviceSlug, 'emulator')
  const child = spawn(pythonExe, ['-u', emulatorScript, '--config', configPath], {
    cwd: projectRoot,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  emulatorProcess = child

  child.stdout?.on('data', (data: Buffer) => {
    const lines = data.toString().split('\n').filter(Boolean)
    for (const line of lines) {
      console.log(`[emulator] ${line}`)
      appendDeviceLog(logFile, 'emulator', line)
    }
  })

  child.stderr?.on('data', (data: Buffer) => {
    const lines = data.toString().split('\n').filter(Boolean)
    for (const line of lines) {
      console.error(`[emulator:err] ${line}`)
      appendDeviceLog(logFile, 'emulator:err', line)
    }
    emulatorStderr = [...emulatorStderr, ...lines].slice(-15)
  })

  child.on('error', (error) => {
    recordAppEvent('error', 'emulator', `Device emulator process error: ${error.message}`)
  })

  child.on('exit', (code) => {
    console.log(`[emulator] exited with code ${code}`)
    recordAppEvent(code === 0 ? 'info' : 'error', 'emulator', `Device emulator exited with code ${code ?? 'unknown'}`)
    if (emulatorProcess === child) {
      emulatorProcess = null
      emulatorDeviceId = null
    }
  })
}

function resumePersistedEmulator(): void {
  const credentials = readCredentialsFile()
  const deviceName = credentials.device_name
  if (credentials.enrollment_method !== 'emulated' || !credentials.device_id || !deviceName) {
    return
  }

  const configPath = path.join(EMULATOR_DIR, `${deviceName}-config.json`)
  const emulatorCredentialsPath = path.join(EMULATOR_DIR, `${deviceName}.json`)
  if (!fs.existsSync(configPath) || !fs.existsSync(emulatorCredentialsPath)) {
    console.warn(`[emulator] Cannot resume ${deviceName}: saved config or credentials are missing`)
    recordAppEvent('warning', 'emulator', 'Saved device emulator could not resume because local files are missing')
    return
  }

  try {
    const config = JSON.parse(fs.readFileSync(configPath, 'utf-8')) as EmulatorFileConfig
    const emulatorType = config.emulator_type ?? inferEmulatorType(config.os_details)
    startEmulatorProcess(emulatorType, configPath)
    emulatorDeviceId = credentials.device_id
    console.log(`[emulator] Resumed ${deviceName} (${emulatorDeviceId})`)
    recordAppEvent('info', 'emulator', 'Saved device emulator resumed successfully')
  } catch (error) {
    console.error(`[emulator] Failed to resume ${deviceName}:`, error)
    recordAppEvent('error', 'emulator', `Saved device emulator failed to resume: ${error instanceof Error ? error.message : 'unknown error'}`)
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
      // Abort early if the emulator process has already exited (e.g. a python
      // import failure like missing httpx) so the error surfaces immediately
      // instead of waiting out the timeout.
      if (!emulatorProcess) {
        resolve(null)
        return
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
  if (!hasSingleInstanceLock) return
  const isFirstLaunch = !fs.existsSync(getAppLogFile())
  if (isFirstLaunch) {
    recordAppEvent('info', 'installation', 'Installation completed; HOMEPOT Agent launched for the first time')
  }
  recordAppEvent('info', 'application', `HOMEPOT Agent ${app.getVersion()} started`)
  registerIpcHandlers()
  adoptExistingEmulatorDevice()
  resumePersistedEmulator()
  startDeviceAgentIfProvisioned()
  createWindow()
  createTray()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('before-quit', () => {
  recordAppEvent('info', 'application', 'HOMEPOT Agent is stopping')
  killEmulator()
  killAgent()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
