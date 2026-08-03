import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppProvider } from '../context/AppContext'
import Activity from '../views/Activity'

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

function mockActivityData() {
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
    if (url.includes('/audit')) {
      return ok({
        data: [
          {
            id: 1,
            event_type: 'permission_change',
            description: "Permission 'root_access' granted by admin@example.com",
            created_at: '2026-08-03T10:00:00.000Z',
            ip_address: null,
            metadata: null,
          },
        ],
      })
    }
    if (url.includes('/jobs')) {
      return ok({
        data: [
          {
            job_id: 'j1',
            action: 'Update POS payment config',
            description: 'Automated background task',
            status: 'completed',
            priority: 'normal',
            created_at: '2026-08-03T10:00:00.000Z',
            completed_at: null,
            result: null,
            error_message: null,
          },
        ],
      })
    }
    if (url.includes('/alerts')) {
      return ok({
        data: [
          {
            id: 1,
            title: 'High Latency: 612ms',
            description: 'Network latency exceeded threshold',
            severity: 'critical',
            category: 'network',
            status: 'active',
            timestamp: '2026-08-03T10:00:00.000Z',
            ai_recommendation: null,
            ai_confidence: null,
          },
        ],
      })
    }
    if (url.includes('/push-history')) {
      return ok({
        data: [
          {
            id: 1,
            timestamp: '2026-08-03T10:00:00.000Z',
            parameter_name: 'push_command:APPLY_CONFIG',
            old_value: null,
            new_value: { command: 'APPLY_CONFIG' },
            change_reason: 'Push command APPLY_CONFIG executed',
            changed_by: 'agent',
            was_successful: true,
          },
        ],
      })
    }
    return ok({ data: [] })
  })
}

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <MemoryRouter initialEntries={['/activity']}>
      <AppProvider>{ui}</AppProvider>
    </MemoryRouter>,
  )
}

describe('Activity', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('renders Live Logs by default', async () => {
    mockActivityData()
    renderWithProviders(<Activity />)
    expect(await screen.findByText('Activity & History')).toBeInTheDocument()
    expect(await screen.findByText('WAN link flapping detected')).toBeInTheDocument()
  })

  it('switches tabs and shows each activity type', async () => {
    mockActivityData()
    renderWithProviders(<Activity />)
    await screen.findByText('WAN link flapping detected')

    fireEvent.click(screen.getByText('Audit'))
    expect(await screen.findByText('permission_change')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Jobs'))
    expect(await screen.findByText('Update POS payment config')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Alerts'))
    expect(await screen.findByText('High Latency: 612ms')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Push'))
    expect(await screen.findByText('push_command:APPLY_CONFIG')).toBeInTheDocument()
  })

  it('shows empty state when there is no data', async () => {
    mockFetch.mockImplementation(() => ok({ data: [] }))
    renderWithProviders(<Activity />)
    expect(await screen.findByText('No live logs yet.')).toBeInTheDocument()
  })
})
