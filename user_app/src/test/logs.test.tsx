import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppProvider } from '../context/AppContext'
import Logs from '../views/Logs'

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

function mockLogsData() {
  mockFetch.mockImplementation((url: string) => {
    if (url.includes('/logs')) {
      return ok({
        data: [
          {
            id: 1,
            timestamp: '2026-08-03T10:00:00.000Z',
            category: 'network',
            severity: 'warning',
            error_code: null,
            error_message: 'WAN link flapping detected',
            resolved: false,
          },
        ],
      })
    }
    return ok({ data: [] })
  })
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
    mockFetch.mockReset()
  })

  it('renders device logs', async () => {
    mockLogsData()
    renderWithProviders(<Logs />)
    expect(await screen.findByText('Device Logs')).toBeInTheDocument()
    expect(await screen.findByText('WAN link flapping detected')).toBeInTheDocument()
  })

  it('shows empty state when there is no data', async () => {
    mockFetch.mockImplementation(() => ok({ data: [] }))
    renderWithProviders(<Logs />)
    expect(await screen.findByText('No logs yet.')).toBeInTheDocument()
  })
})
