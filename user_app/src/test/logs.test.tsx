import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppProvider } from '../context/AppProvider'
import Logs from '../views/Logs'

const getRecentLogs = vi.fn()
const fetchDeviceLogs = vi.fn()
const fetchDeviceAuditEvents = vi.fn()
const fetchDeviceCommandHistory = vi.fn()
const fetchDeviceAlerts = vi.fn()

vi.mock('../services/credentialStorage', () => ({
  credentialStorage: {
    getDeviceId: vi.fn().mockResolvedValue('test-device'),
    getApiKey: vi.fn().mockResolvedValue('test-key'),
    getMetadata: vi.fn().mockResolvedValue('mock-value'),
    isProvisioned: vi.fn().mockResolvedValue(true),
    clear: vi.fn().mockResolvedValue(undefined),
  },
}))

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>()
  return {
    ...actual,
    fetchDeviceLogs: (...args: Parameters<typeof actual.fetchDeviceLogs>) =>
      fetchDeviceLogs(...args),
    fetchDeviceAuditEvents: (
      ...args: Parameters<typeof actual.fetchDeviceAuditEvents>
    ) => fetchDeviceAuditEvents(...args),
    fetchDeviceCommandHistory: (
      ...args: Parameters<typeof actual.fetchDeviceCommandHistory>
    ) => fetchDeviceCommandHistory(...args),
    fetchDeviceAlerts: (...args: Parameters<typeof actual.fetchDeviceAlerts>) =>
      fetchDeviceAlerts(...args),
  }
})

function mockLogsData() {
  getRecentLogs.mockResolvedValue([
    {
      id: 'event-1',
      timestamp: '2026-08-03T10:00:00.000Z',
      category: 'application',
      level: 'info',
      message: 'HOMEPOT Agent started',
    },
  ])
}

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <MemoryRouter initialEntries={['/logs']}>
      <AppProvider>{ui}</AppProvider>
    </MemoryRouter>,
  )
}

describe('Logs', () => {
  beforeEach(() => {
    getRecentLogs.mockReset()
    getRecentLogs.mockResolvedValue([])
    fetchDeviceLogs.mockReset()
    fetchDeviceLogs.mockResolvedValue([])
    fetchDeviceAuditEvents.mockReset()
    fetchDeviceAuditEvents.mockResolvedValue([])
    fetchDeviceCommandHistory.mockReset()
    fetchDeviceCommandHistory.mockResolvedValue([])
    fetchDeviceAlerts.mockReset()
    fetchDeviceAlerts.mockResolvedValue([])
    window.electronAPI = {
      app: { getRecentLogs },
    } as unknown as NonNullable<Window['electronAPI']>
  })

  it('renders the latest local application logs', async () => {
    mockLogsData()
    renderWithProviders(<Logs />)
    expect(await screen.findByText('Application Logs')).toBeInTheDocument()
    expect(await screen.findByText('HOMEPOT Agent started')).toBeInTheDocument()
    expect(getRecentLogs).toHaveBeenCalledWith(15)
  })

  it('shows empty state when there is no data', async () => {
    getRecentLogs.mockResolvedValue([])
    renderWithProviders(<Logs />)
    expect(await screen.findByText('No application events yet.')).toBeInTheDocument()
  })

  it('renders backend device logs above application events', async () => {
    fetchDeviceLogs.mockResolvedValue([
      {
        id: 1,
        timestamp: '2026-08-03T10:00:00.000Z',
        category: 'network',
        severity: 'warning',
        error_code: 'WAN-1',
        error_message: 'WAN link flapping detected',
        resolved: false,
      },
    ])
    getRecentLogs.mockResolvedValue([])
    renderWithProviders(<Logs />)
    expect(await screen.findByText('Device Logs')).toBeInTheDocument()
    expect(await screen.findByText('WAN link flapping detected')).toBeInTheDocument()
    expect(fetchDeviceLogs).toHaveBeenCalledWith('test-device', 'test-key', 50)
  })

  it('renders the device audit trail', async () => {
    fetchDeviceAuditEvents.mockResolvedValue([
      {
        id: 2,
        event_type: 'permission_change',
        description: 'Root access granted by owner',
        event_metadata: { permission: 'root_access', granted: true },
        created_at: '2026-08-03T10:05:00.000Z',
      },
    ])
    renderWithProviders(<Logs />)
    expect(await screen.findByText('Audit Trail')).toBeInTheDocument()
    expect(await screen.findByText('Permission Change')).toBeInTheDocument()
    expect(await screen.findByText('Root access granted by owner')).toBeInTheDocument()
    expect(fetchDeviceAuditEvents).toHaveBeenCalledWith('test-device', 'test-key', 50)
  })

  it('renders command history for the device', async () => {
    fetchDeviceCommandHistory.mockResolvedValue([
      {
        command_id: 'cmd-1',
        command_type: 'restart',
        payload: { mode: 'soft' },
        status: 'completed',
        result: { ok: true },
        created_at: '2026-08-03T10:06:00.000Z',
        sent_at: null,
        executed_at: '2026-08-03T10:06:05.000Z',
      },
    ])
    renderWithProviders(<Logs />)
    expect(await screen.findByText('Command History')).toBeInTheDocument()
    expect(await screen.findByText('Restart')).toBeInTheDocument()
    expect(fetchDeviceCommandHistory).toHaveBeenCalledWith('test-device', 'test-key', 50)
  })

  it('hints that command history requires the Manage permission when gated', async () => {
    fetchDeviceCommandHistory.mockRejectedValue(
      new (await import('../services/api')).ApiError('Manage required', 403),
    )
    renderWithProviders(<Logs />)
    expect(
      await screen.findByText(/grant Manage access to this device/i),
    ).toBeInTheDocument()
  })

  it('renders alerts for the device', async () => {
    fetchDeviceAlerts.mockResolvedValue([
      {
        id: 1,
        title: 'Disk usage high',
        description: 'Disk at 92%',
        severity: 'high',
        category: 'hardware',
        status: 'active',
        timestamp: '2026-08-03T10:10:00.000Z',
        resolved_at: null,
        resolved_by: null,
      },
    ])
    renderWithProviders(<Logs />)
    expect(await screen.findByText('Alerts')).toBeInTheDocument()
    expect(await screen.findByText('Disk usage high')).toBeInTheDocument()
    expect(fetchDeviceAlerts).toHaveBeenCalledWith('test-device', 'test-key', 50)
  })

  it('hints that diagnostics require the Monitor permission when gated', async () => {
    fetchDeviceAlerts.mockRejectedValue(
      new (await import('../services/api')).ApiError('Monitor required', 403),
    )
    renderWithProviders(<Logs />)
    expect(
      await screen.findByText(/grant Monitor access to this device/i),
    ).toBeInTheDocument()
  })
})
