import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import PermissionConsentPrompt from '../components/PermissionConsentPrompt'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

vi.mock('../services/credentialStorage', () => ({
  credentialStorage: {
    getDeviceId: vi.fn().mockResolvedValue('test-device'),
    getApiKey: vi.fn().mockResolvedValue('test-key'),
  },
}))

function ok(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
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
      .mockResolvedValueOnce(ok([pendingCommand])) // GET /pending
    render(<PermissionConsentPrompt />)
    expect(await screen.findByText('Permission request')).toBeInTheDocument()
    expect(screen.getByText(/admin@example\.com/)).toBeInTheDocument()
    expect(screen.getByText(/Root \/ Full Access/)).toBeInTheDocument()
    expect(screen.getByText('Allow')).toBeInTheDocument()
    expect(screen.getByText('Deny')).toBeInTheDocument()
  })

  it('does not render when no request_permission command is pending', async () => {
    mockFetch
      .mockResolvedValueOnce(ok([])) // GET /pending
    render(<PermissionConsentPrompt />)
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled()
    })
    expect(screen.queryByText('Permission request')).not.toBeInTheDocument()
  })

  it('grants the permission on accept', async () => {
    mockFetch
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

  it('denies the permission on deny', async () => {
    mockFetch
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
      .mockResolvedValueOnce(ok([revokeCommand])) // GET /pending
    render(<PermissionConsentPrompt />)
    expect(await screen.findByText('Revoke access requested')).toBeInTheDocument()
    expect(screen.getByText('Approve revocation')).toBeInTheDocument()
  })
})
