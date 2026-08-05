import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppProvider } from '../context/AppContext'
import Logs from '../views/Logs'

const getRecentLogs = vi.fn()

vi.mock('../services/credentialStorage', () => ({
  credentialStorage: {
    getDeviceId: vi.fn().mockResolvedValue('test-device'),
    getApiKey: vi.fn().mockResolvedValue('test-key'),
    getMetadata: vi.fn().mockResolvedValue('mock-value'),
    isProvisioned: vi.fn().mockResolvedValue(true),
    clear: vi.fn().mockResolvedValue(undefined),
  },
}))

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
})
