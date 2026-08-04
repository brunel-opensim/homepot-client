import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppProvider } from '../context/AppContext'
import HomeDashboard from '../views/HomeDashboard'
import DeviceInfo from '../views/DeviceInfo'
import Permissions from '../views/Permissions'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

vi.mock('../services/credentialStorage', () => ({
  credentialStorage: {
    getDeviceId: vi.fn().mockResolvedValue('test-device'),
    getApiKey: vi.fn().mockResolvedValue('test-key'),
    getMetadata: vi.fn().mockResolvedValue('mock-value'),
    isProvisioned: vi.fn().mockResolvedValue(true),
    clear: vi.fn().mockResolvedValue(undefined),
  },
}))

function ok(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
}

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <AppProvider>{ui}</AppProvider>
    </MemoryRouter>,
  )
}

describe('HomeDashboard', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  function statusOk(overrides: Partial<{ lifecycle_state: string; connectivity_state: string; health_state: string; last_heartbeat_at: string | null }> = {}) {
    return ok({
      data: {
        lifecycle_state: 'active',
        connectivity_state: 'online',
        health_state: 'good',
        last_heartbeat_at: '2026-08-03T12:34:56.000Z',
        ...overrides,
      },
    })
  }

  function metricsOk(overrides: Partial<{ cpu_percent: number | null; memory_percent: number | null; disk_percent: number | null; network_latency_ms: number | null; uptime_seconds: number | null; timestamp: string | null }> = {}) {
    return ok({
      data: {
        cpu_percent: 42,
        memory_percent: 61,
        disk_percent: 28,
        network_latency_ms: 12.5,
        uptime_seconds: 3725,
        timestamp: '2026-08-03T12:34:56.000Z',
        ...overrides,
      },
    })
  }

  function routeDeviceApi(status: Promise<Response>, metrics: Promise<Response> = metricsOk(), failStatus = false) {
    mockFetch.mockImplementation((url: string) => {
      if (String(url).includes('/permissions')) {
        return ok({ data: { permissions: {}, capabilities: {} } })
      }
      if (String(url).includes('/metrics')) {
        return metrics
      }
      if (String(url).includes('/status')) {
        return failStatus ? Promise.reject(new Error('Network error')) : status
      }
      return ok({ data: [] })
    })
  }

  it('renders header and gauges', async () => {
    routeDeviceApi(statusOk())
    renderWithProviders(<HomeDashboard />)
    expect(await screen.findByText('HOMEPOT Agent')).toBeInTheDocument()
    expect(await screen.findByText('SECURE — ONLINE')).toBeInTheDocument()
    expect(screen.getByText('CPU')).toBeInTheDocument()
    expect(screen.getByText('Memory')).toBeInTheDocument()
    expect(screen.getByText('Disk')).toBeInTheDocument()
  })

  it('renders live metrics from backend', async () => {
    routeDeviceApi(statusOk())
    renderWithProviders(<HomeDashboard />)
    expect(await screen.findByText('42%')).toBeInTheDocument()
    expect(await screen.findByText('61%')).toBeInTheDocument()
    expect(await screen.findByText('28%')).toBeInTheDocument()
    expect(screen.getByText('12.5ms')).toBeInTheDocument()
    expect(screen.getByText('1h 2m')).toBeInTheDocument()
  })

  it('renders backend heartbeat timestamp', async () => {
    routeDeviceApi(statusOk())
    renderWithProviders(<HomeDashboard />)
    expect(await screen.findByText('SECURE — ONLINE')).toBeInTheDocument()
    const expected = new Date('2026-08-03T12:34:56.000Z').toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
    expect(screen.getByText(expected)).toBeInTheDocument()
  })

  it('shows offline state when backend returns offline', async () => {
    routeDeviceApi(statusOk({ connectivity_state: 'offline', last_heartbeat_at: null }))
    renderWithProviders(<HomeDashboard />)
    expect(await screen.findByText('OFFLINE')).toBeInTheDocument()
  })

  it('shows suspended banner when lifecycle is suspended', async () => {
    routeDeviceApi(statusOk({ lifecycle_state: 'suspended', connectivity_state: 'offline', last_heartbeat_at: null }))
    renderWithProviders(<HomeDashboard />)
    expect(await screen.findByText('DEVICE SUSPENDED')).toBeInTheDocument()
  })

  it('renders TabBar with navigation links', async () => {
    routeDeviceApi(statusOk())
    renderWithProviders(<HomeDashboard />)
    expect(await screen.findByText('Home')).toBeInTheDocument()
    expect(screen.getByText('Perms')).toBeInTheDocument()
    expect(screen.getByText('Logs')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('shows unknown state when fetch fails', async () => {
    routeDeviceApi(statusOk(), metricsOk(), true)
    renderWithProviders(<HomeDashboard />)
    expect(await screen.findByText('HOMEPOT Agent')).toBeInTheDocument()
    expect(await screen.findByText('OFFLINE')).toBeInTheDocument()
  })
})

describe('DeviceInfo', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  function routeDeviceApi(device: unknown, deviceFails = false) {
    mockFetch.mockImplementation((url: string) => {
      if (String(url).includes('/permissions')) {
        return ok({ data: { permissions: {}, capabilities: {} } })
      }
      if (deviceFails) return Promise.reject(new Error('Network error'))
      return ok(device)
    })
  }

  it('renders DNA table with backend data', async () => {
    routeDeviceApi({
      device_id: 'test-device',
      name: 'Backend Device',
      site_id: 'site-001',
      device_type: 'pos_terminal',
      mac_address: '00:11:22:33:44:55',
      local_ip: '192.168.1.100',
      wan_ip: '203.0.113.10',
      os_details: 'linux',
      firmware_version: '1.0.0',
      lifecycle_state: 'active',
      connectivity_state: 'online',
    })
    renderWithProviders(<DeviceInfo />)
    expect(await screen.findByText('HOMEPOT Agent')).toBeInTheDocument()
    expect(await screen.findByText('Backend Device')).toBeInTheDocument()
    expect(screen.getByText('site-001')).toBeInTheDocument()
    expect(screen.getByText('00:11:22:33:44:55')).toBeInTheDocument()
    expect(screen.getByText('192.168.1.100')).toBeInTheDocument()
    expect(screen.getByText('Linux')).toBeInTheDocument()
    expect(screen.getByText('Pos Terminal')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('renders fallback values when backend fetch fails', async () => {
    const credStorageModule = await import('../services/credentialStorage')
    vi.mocked(credStorageModule.credentialStorage.getMetadata).mockResolvedValue(null)
    routeDeviceApi(null, true)
    renderWithProviders(<DeviceInfo />)
    expect(await screen.findByText('HOMEPOT Agent')).toBeInTheDocument()
    expect(await screen.findByText('My-Device')).toBeInTheDocument()
    expect(screen.getAllByText('—')).toHaveLength(3) // MAC, IP, Site ID fallbacks
    expect(screen.getByText('Web')).toBeInTheDocument()
  })

  it('renders unpair button', async () => {
    routeDeviceApi({
      device_id: 'test-device',
      name: 'Test Device',
      device_type: 'pos_terminal',
      os_details: 'linux',
      lifecycle_state: 'active',
    })
    renderWithProviders(<DeviceInfo />)
    expect(await screen.findByText('HOMEPOT Agent')).toBeInTheDocument()
    expect(await screen.findByText(/Disconnect.*Unpair/)).toBeInTheDocument()
  })
})

describe('Permissions', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows override notice when server permissions change externally', async () => {
    mockFetch.mockImplementation(() =>
      ok({
        data: {
          permissions: { root_access: true },
          capabilities: { root_access: true },
        },
      }),
    )
    renderWithProviders(<Permissions />)
    await vi.advanceTimersByTimeAsync(100) // creds-ready interval fires initial load
    expect(await screen.findByText('Permissions & Access Control')).toBeInTheDocument()

    mockFetch.mockImplementation(() =>
      ok({
        data: {
          permissions: { root_access: false },
          capabilities: { root_access: true },
        },
      }),
    )
    await vi.advanceTimersByTimeAsync(15000) // background refresh detects change
    expect(await screen.findByText(/operator or administrator has updated/)).toBeInTheDocument()
  })

  it('does not show override notice when permissions are unchanged', async () => {
    mockFetch.mockImplementation(() =>
      ok({
        data: {
          permissions: { root_access: true },
          capabilities: { root_access: true },
        },
      }),
    )
    renderWithProviders(<Permissions />)
    await vi.advanceTimersByTimeAsync(100)
    expect(await screen.findByText('Permissions & Access Control')).toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(15000)
    expect(screen.queryByText(/operator or administrator has updated/)).not.toBeInTheDocument()
  })
})
