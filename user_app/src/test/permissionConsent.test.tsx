import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import PermissionConsentPrompt from '../components/PermissionConsentPrompt'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

vi.mock('../services/credentialStorage', () => ({
  credentialStorage: {
    getDeviceId: vi.fn().mockResolvedValue('test-device'),
    getApiKey: vi.fn().mockResolvedValue('test-key'),
    getMetadata: vi.fn().mockResolvedValue('self-enrolled'),
  },
}))

function ok(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
}

// GET /permissions response: root_access is supported on this (mock) device.
function permissionsOk() {
  return ok({ data: { permissions: {}, capabilities: { root_access: true } } })
}

const pendingCommand = {
  command_id: 'cmd-1',
  command_type: 'request_permission',
  payload: {
    data: { permission: 'root_access', action: 'grant', requested_by: 'admin@example.com' },
  },
  status: 'pending',
  created_at: '2026-08-03T10:00:00.000Z',
}

describe('PermissionConsentPrompt', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('shows a prompt when a request_permission command is pending', async () => {
    mockFetch
      .mockResolvedValueOnce(permissionsOk()) // GET /permissions
      .mockResolvedValueOnce(ok([pendingCommand])) // GET /pending
    render(<PermissionConsentPrompt />)
    expect(await screen.findByText('Permission request')).toBeInTheDocument()
    expect(screen.getByText(/admin@example\.com/)).toBeInTheDocument()
    expect(screen.getByText(/Manage device \(root\/sudo access\)/)).toBeInTheDocument()
    expect(screen.getByText('Allow')).toBeInTheDocument()
    expect(screen.getByText('Deny')).toBeInTheDocument()
  })

  it('does not render when no request_permission command is pending', async () => {
    mockFetch
      .mockResolvedValueOnce(permissionsOk()) // GET /permissions
      .mockResolvedValueOnce(ok([])) // GET /pending
    render(<PermissionConsentPrompt />)
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled()
    })
    expect(screen.queryByText('Permission request')).not.toBeInTheDocument()
  })

  it('grants the permission on accept', async () => {
    mockFetch
      .mockResolvedValueOnce(permissionsOk()) // GET /permissions
      .mockResolvedValueOnce(ok([pendingCommand])) // GET /pending
      .mockResolvedValueOnce(ok({})) // PATCH permissions
      .mockResolvedValueOnce(ok({})) // audit
      .mockResolvedValueOnce(ok({})) // PUT status
    render(<PermissionConsentPrompt />)
    fireEvent.click(await screen.findByText('Allow'))

    await waitFor(() => {
      const patch = mockFetch.mock.calls.find(([, init]) => init?.method === 'PATCH')
      expect(patch).toBeTruthy()
      expect(JSON.parse(String(patch![1].body))).toEqual({ permissions: { root_access: true } })
    })
    await waitFor(() => {
      const put = mockFetch.mock.calls.find(([, init]) => init?.method === 'PUT')
      expect(put).toBeTruthy()
      const body = JSON.parse(String(put![1].body))
      expect(body.status).toBe('completed')
      expect(body.result).toEqual({
        permission: 'root_access',
        action: 'grant',
        granted: true,
        message: "Permission 'root_access' granted by device owner",
      })
    })
    await waitFor(() => {
      expect(screen.queryByText('Permission request')).not.toBeInTheDocument()
    })
  })

  it('grants the whole monitor group when accepting a monitor request', async () => {
    const monitorCommand = {
      ...pendingCommand,
      payload: {
        data: { permission: 'command_execution', action: 'grant', requested_by: 'admin@example.com' },
      },
    }
    mockFetch
      .mockResolvedValueOnce(
        ok({
          data: {
            permissions: {},
            capabilities: {
              command_execution: true,
              filesystem_access: true,
              process_monitoring: true,
              network_monitoring: true,
            },
          },
        }),
      ) // GET /permissions
      .mockResolvedValueOnce(ok([monitorCommand])) // GET /pending
      .mockResolvedValueOnce(ok({})) // PATCH permissions
      .mockResolvedValueOnce(ok({})) // audit
      .mockResolvedValueOnce(ok({})) // PUT status
    render(<PermissionConsentPrompt />)
    expect(await screen.findByText('Permission request')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Allow'))

    await waitFor(() => {
      const patch = mockFetch.mock.calls.find(([, init]) => init?.method === 'PATCH')
      expect(patch).toBeTruthy()
      expect(JSON.parse(String(patch![1].body))).toEqual({
        permissions: {
          command_execution: true,
          filesystem_access: true,
          process_monitoring: true,
          network_monitoring: true,
        },
      })
    })
  })

  it('denies the permission on deny', async () => {
    mockFetch
      .mockResolvedValueOnce(permissionsOk()) // GET /permissions
      .mockResolvedValueOnce(ok([pendingCommand])) // GET /pending
      .mockResolvedValueOnce(ok({})) // PATCH permissions
      .mockResolvedValueOnce(ok({})) // audit
      .mockResolvedValueOnce(ok({})) // PUT status
    render(<PermissionConsentPrompt />)
    fireEvent.click(await screen.findByText('Deny'))

    await waitFor(() => {
      const patch = mockFetch.mock.calls.find(([, init]) => init?.method === 'PATCH')
      expect(patch).toBeTruthy()
      expect(JSON.parse(String(patch![1].body))).toEqual({ permissions: { root_access: false } })
    })
    await waitFor(() => {
      const put = mockFetch.mock.calls.find(([, init]) => init?.method === 'PUT')
      const body = JSON.parse(String(put![1].body))
      expect(body.result.granted).toBe(false)
    })
  })

  it('shows a revoke prompt for revoke actions', async () => {
    const revokeCommand = {
      ...pendingCommand,
      payload: {
        data: { permission: 'process_monitoring', action: 'revoke', requested_by: 'admin@example.com' },
      },
    }
    mockFetch
      .mockResolvedValueOnce(permissionsOk()) // GET /permissions
      .mockResolvedValueOnce(ok([revokeCommand])) // GET /pending
    render(<PermissionConsentPrompt />)
    expect(await screen.findByText('Revoke access requested')).toBeInTheDocument()
    expect(screen.getByText('Approve revocation')).toBeInTheDocument()
  })

  it('shows a not-supported notice for unsupported permissions', async () => {
    // capabilities omit root_access → the grant can't succeed.
    mockFetch
      .mockResolvedValueOnce(ok({ data: { permissions: {}, capabilities: {} } })) // GET /permissions
      .mockResolvedValueOnce(ok([pendingCommand])) // GET /pending (root_access grant)
    render(<PermissionConsentPrompt />)
    expect(await screen.findByText(/not supported on this device/)).toBeInTheDocument()
    expect(screen.queryByText('Allow')).not.toBeInTheDocument()
    expect(screen.queryByText('Deny')).not.toBeInTheDocument()
  })

  it('resolves a follow-up request without hanging', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const secondCommand = { ...pendingCommand, command_id: 'cmd-2' }
    mockFetch
      .mockResolvedValueOnce(permissionsOk()) // GET /permissions (mount)
      .mockResolvedValueOnce(ok([pendingCommand])) // GET /pending (first request)
      .mockResolvedValueOnce(ok({})) // PATCH (first accept)
      .mockResolvedValueOnce(ok({})) // audit
      .mockResolvedValueOnce(ok({})) // PUT status -> completed
      .mockResolvedValueOnce(permissionsOk()) // GET /permissions (10s poll: loadCapabilities)
      .mockResolvedValueOnce(ok([secondCommand])) // GET /pending (10s poll: second request)
      .mockResolvedValueOnce(ok({})) // PATCH (second accept)
      .mockResolvedValueOnce(ok({})) // audit
      .mockResolvedValueOnce(ok({})) // PUT status -> completed
    render(<PermissionConsentPrompt />)

    fireEvent.click(await screen.findByText('Allow'))
    await waitFor(() => {
      expect(screen.queryByText('Permission request')).not.toBeInTheDocument()
    })

    // The second request arrives on the next poll and must NOT be stuck busy.
    await vi.advanceTimersByTimeAsync(10000)
    expect(await screen.findByText('Permission request')).toBeInTheDocument()
    const allow = screen.getByText('Allow')
    expect(allow).toBeEnabled()

    fireEvent.click(allow)
    await waitFor(() => {
      expect(screen.queryByText('Permission request')).not.toBeInTheDocument()
    })
    vi.useRealTimers()
  })

  it('completes an unsupported request as failed on close', async () => {
    mockFetch
      .mockResolvedValueOnce(ok({ data: { permissions: {}, capabilities: {} } })) // GET /permissions
      .mockResolvedValueOnce(ok([pendingCommand])) // GET /pending (root_access grant)
      .mockResolvedValueOnce(ok({})) // PUT status (failed)
    render(<PermissionConsentPrompt />)
    fireEvent.click(await screen.findByText('Close'))

    await waitFor(() => {
      const put = mockFetch.mock.calls.find(([, init]) => init?.method === 'PUT')
      expect(put).toBeTruthy()
      const body = JSON.parse(String(put![1].body))
      expect(body.status).toBe('failed')
      expect(body.result).toMatchObject({ granted: false })
    })
    await waitFor(() => {
      expect(screen.queryByText('Permission request')).not.toBeInTheDocument()
    })
  })

  describe('managed (root_access) elevation lifecycle', () => {
    let events: string[]

    function mockElevationBridge(overrides: Partial<Record<'install' | 'deprovision', unknown>> = {}) {
      // Record the order of IPC elevation calls and fetch methods on a shared
      // timeline so tests can assert install-before-grant / revoke-then-strip.
      events = []
      const elevation = {
        install: vi.fn().mockImplementation(async () => {
          events.push('elevation:install')
          return overrides.install ?? { installed: true, reason: null }
        }),
        deprovision: vi.fn().mockImplementation(async () => {
          events.push('elevation:deprovision')
          return overrides.deprovision ?? { deprovisioned: true, reason: null }
        }),
        supported: vi.fn().mockResolvedValue(true),
        status: vi.fn().mockResolvedValue({ supported: true, installed: true, provisioned: true, ops: ['restart', 'shutdown'] }),
      }
      Object.defineProperty(window, 'electronAPI', {
        value: { elevation },
        configurable: true,
      })
      const wrappedFetch = vi.fn((...args: Parameters<typeof fetch>) => {
        events.push(`fetch:${String(args[1]?.method ?? 'GET')}`)
        return mockFetch(...args)
      })
      globalThis.fetch = wrappedFetch
      return elevation
    }

    afterEach(() => {
      delete (window as { electronAPI?: unknown }).electronAPI
      globalThis.fetch = mockFetch
    })

    it('installs OS elevation before committing a Manage grant', async () => {
      const elevation = mockElevationBridge()
      mockFetch
        .mockResolvedValueOnce(permissionsOk()) // GET /permissions
        .mockResolvedValueOnce(ok([pendingCommand])) // GET /pending (root_access grant)
        .mockResolvedValueOnce(ok({})) // PATCH permissions
        .mockResolvedValueOnce(ok({})) // audit
        .mockResolvedValueOnce(ok({})) // PUT status
      render(<PermissionConsentPrompt />)
      fireEvent.click(await screen.findByText('Allow'))

      await waitFor(() => expect(elevation.install).toHaveBeenCalled())
      await waitFor(() => expect(events).toContain('fetch:PATCH'))
      expect(events.indexOf('elevation:install')).toBeLessThan(events.indexOf('fetch:PATCH'))
    })

    it('fails the Manage grant when OS elevation cannot be installed', async () => {
      const elevation = mockElevationBridge({ install: { installed: false, reason: 'Elevation setup cancelled' } })
      mockFetch
        .mockResolvedValueOnce(permissionsOk()) // GET /permissions
        .mockResolvedValueOnce(ok([pendingCommand])) // GET /pending
        .mockResolvedValueOnce(ok({})) // PUT status (failed -> resolves request)
      render(<PermissionConsentPrompt />)
      fireEvent.click(await screen.findByText('Allow'))

      await waitFor(() => expect(elevation.install).toHaveBeenCalled())
      await waitFor(() => {
        const put = mockFetch.mock.calls.find(([, init]) => init?.method === 'PUT')
        expect(put).toBeTruthy()
        const body = JSON.parse(String(put![1].body))
        expect(body.status).toBe('failed')
        expect(String(body.result.message)).toContain('Elevation setup cancelled')
      })
      expect(events).not.toContain('fetch:PATCH')
    })

    it('strips OS elevation only after the Manage revoke is committed', async () => {
      const elevation = mockElevationBridge()
      const revokeCommand = {
        ...pendingCommand,
        payload: {
          data: { permission: 'root_access', action: 'revoke', requested_by: 'admin@example.com' },
        },
      }
      mockFetch
        .mockResolvedValueOnce(permissionsOk()) // GET /permissions
        .mockResolvedValueOnce(ok([revokeCommand])) // GET /pending (revoke request)
        .mockResolvedValueOnce(ok({})) // PATCH permissions
        .mockResolvedValueOnce(ok({})) // audit
        .mockResolvedValueOnce(ok({})) // PUT status
      render(<PermissionConsentPrompt />)
      fireEvent.click(await screen.findByText('Approve revocation'))

      await waitFor(() => expect(elevation.deprovision).toHaveBeenCalled())
      await waitFor(() => expect(events).toContain('fetch:PATCH'))
      expect(events.indexOf('fetch:PATCH')).toBeLessThan(events.indexOf('elevation:deprovision'))
    })

    it('does not install OS elevation for emulated devices', async () => {
      // Emulated enrollment simulates the whole permission flow in-process and
      // must never surface the OS admin prompt / sudo layer.
      const { credentialStorage: _unused } = await import('../services/credentialStorage')
      vi.mocked(_unused.getMetadata).mockResolvedValue('emulated')
      const elevation = mockElevationBridge()
      mockFetch
        .mockResolvedValueOnce(permissionsOk()) // GET /permissions
        .mockResolvedValueOnce(ok([pendingCommand])) // GET /pending (root_access grant)
        .mockResolvedValueOnce(ok({})) // PATCH permissions
        .mockResolvedValueOnce(ok({})) // audit
        .mockResolvedValueOnce(ok({})) // PUT status
      render(<PermissionConsentPrompt />)
      fireEvent.click(await screen.findByText('Allow'))

      await waitFor(() => expect(events).toContain('fetch:PATCH'))
      expect(elevation.install).not.toHaveBeenCalled()
    })
  })
})
