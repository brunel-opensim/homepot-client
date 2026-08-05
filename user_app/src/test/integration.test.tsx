import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import App from '../App'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

beforeEach(() => {
  mockFetch.mockReset()
  localStorage.clear()
  sessionStorage.clear()
  delete window.electronAPI
  window.history.pushState({}, '', '/')
})

function ok(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
}

describe('App routing', () => {
  it('redirects unprovisioned user from / to setup wizard', async () => {
    render(<App />)
    expect(await screen.findByText('Step 1 of 4')).toBeInTheDocument()
  })

  it('redirects provisioned user from / to dashboard', async () => {
    localStorage.setItem('homepot_device_id', 'pos-001')
    sessionStorage.setItem('homepot_api_key', 'test-key')
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/pending')) {
        return ok([])
      }
      if (url.includes('/metrics')) {
        return ok({
          data: {
            cpu_percent: 10,
            memory_percent: 20,
            disk_percent: 30,
            network_latency_ms: 5,
            uptime_seconds: 3600,
            timestamp: new Date().toISOString(),
          },
        })
      }
      return ok({
        data: {
          lifecycle_state: 'active',
          connectivity_state: 'online',
          health_state: 'good',
          last_heartbeat_at: new Date().toISOString(),
        },
      })
    })
    render(<App />)
    expect(await screen.findByText('SECURE — ONLINE')).toBeInTheDocument()
  })

  it('clears invalid credentials and redirects to setup wizard', async () => {
    localStorage.setItem('homepot_device_id', 'pos-001')
    sessionStorage.setItem('homepot_api_key', 'stale-key')
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/permissions')) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: 'Invalid Device ID' }), { status: 401 }),
        )
      }
      return ok([])
    })
    render(<App />)
    expect(await screen.findByText('Step 1 of 4')).toBeInTheDocument()
    await waitFor(() => {
      expect(localStorage.getItem('homepot_device_id')).toBeNull()
    })
    expect(sessionStorage.getItem('homepot_api_key')).toBeNull()
  })

  it('keeps credentials when backend is unreachable', async () => {
    localStorage.setItem('homepot_device_id', 'pos-001')
    sessionStorage.setItem('homepot_api_key', 'test-key')
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/permissions')) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: 'Server error' }), { status: 500 }),
        )
      }
      if (url.includes('/pending')) {
        return ok([])
      }
      if (url.includes('/metrics')) {
        return ok({
          data: {
            cpu_percent: 10,
            memory_percent: 20,
            disk_percent: 30,
            network_latency_ms: 5,
            uptime_seconds: 3600,
            timestamp: new Date().toISOString(),
          },
        })
      }
      return ok({
        data: {
          lifecycle_state: 'active',
          connectivity_state: 'online',
          health_state: 'good',
          last_heartbeat_at: new Date().toISOString(),
        },
      })
    })
    render(<App />)
    expect(await screen.findByText('SECURE — ONLINE')).toBeInTheDocument()
    expect(localStorage.getItem('homepot_device_id')).toBe('pos-001')
    expect(sessionStorage.getItem('homepot_api_key')).toBe('test-key')
  })

  it('shows device info view at /settings', async () => {
    localStorage.setItem('homepot_device_id', 'pos-001')
    sessionStorage.setItem('homepot_api_key', 'test-key')
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/pending')) {
        return ok([])
      }
      return ok({
        device_id: 'pos-001',
        name: 'Test POS',
        site_id: 'site-alpha',
        device_type: 'pos_terminal',
        mac_address: 'aa:bb:cc:dd:ee:ff',
        local_ip: '10.0.0.5',
        wan_ip: '1.2.3.4',
        os_details: 'Linux',
        firmware_version: '2.0.0',
        lifecycle_state: 'active',
        connectivity_state: 'online',
      })
    })
    window.history.pushState({}, '', '/settings')
    render(<App />)
    await waitFor(() => {
      expect(screen.getByText('Device Info & Settings')).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText('Test POS')).toBeInTheDocument()
    })
    expect(screen.getByText('10.0.0.5')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('shows local application logs at /logs', async () => {
    localStorage.setItem('homepot_device_id', 'pos-001')
    sessionStorage.setItem('homepot_api_key', 'test-key')
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/pending')) {
        return ok([])
      }
      return ok({ data: [] })
    })
    window.electronAPI = {
      app: {
        getRecentLogs: vi.fn().mockResolvedValue([{ id: 'event-1', timestamp: new Date().toISOString(), category: 'application', level: 'info', message: 'User interface ready' }]),
      },
    } as unknown as NonNullable<Window['electronAPI']>
    window.history.pushState({}, '', '/logs')
    render(<App />)
    expect(await screen.findByText('Application Logs')).toBeInTheDocument()
    expect(await screen.findByText('User interface ready')).toBeInTheDocument()
  })

  it('unknown path redirects to /', async () => {
    window.history.pushState({}, '', '/nonexistent')
    render(<App />)
    expect(await screen.findByText('Step 1 of 4')).toBeInTheDocument()
  })
})
