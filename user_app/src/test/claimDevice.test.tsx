import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppContext } from '../context/AppContext'
import ClaimDevice from '../views/ClaimDevice'
import type { AppContextType } from '../context/AppContext'

const mocks = vi.hoisted(() => ({
  save: vi.fn().mockResolvedValue(undefined),
  fetchImpl: vi.fn(),
  setDeviceInfo: vi.fn(),
  setIsProvisioned: vi.fn(),
}))

vi.mock('../services/credentialStorage', () => ({
  credentialStorage: {
    save: mocks.save,
    getDeviceId: vi.fn().mockResolvedValue(null),
    getApiKey: vi.fn().mockResolvedValue(null),
    clear: vi.fn().mockResolvedValue(undefined),
  },
}))

globalThis.fetch = mocks.fetchImpl

function renderClaim() {
  const ctx: AppContextType = {
    deviceInfo: null,
    setDeviceInfo: mocks.setDeviceInfo,
    isProvisioned: false,
    setIsProvisioned: mocks.setIsProvisioned,
    provisionedChecked: true,
    setupState: { siteId: '', deviceName: '', deviceType: '', deviceOs: '', bootstrapKey: '', backendUrl: '' },
    setSetupState: vi.fn(),
    useEmulator: null,
    setUseEmulator: vi.fn(),
    emulatorType: '',
    setEmulatorType: vi.fn(),
    isEmulatorRunning: false,
    setIsEmulatorRunning: vi.fn(),
  }
  return render(
    <MemoryRouter initialEntries={['/claim']}>
      <AppContext.Provider value={ctx}>
        <ClaimDevice />
      </AppContext.Provider>
    </MemoryRouter>,
  )
}

function fillForm() {
  fireEvent.change(screen.getByPlaceholderText('Intent ID from administrator'), { target: { value: 'intent-1' } })
  fireEvent.change(screen.getByPlaceholderText('Claim token from administrator'), { target: { value: 'tok-abc' } })
}

beforeEach(() => {
  mocks.fetchImpl.mockReset()
  mocks.save.mockClear()
  mocks.setDeviceInfo.mockClear()
  mocks.setIsProvisioned.mockClear()
})

describe('ClaimDevice', () => {
  it('renders the claim form with required fields', () => {
    renderClaim()
    expect(screen.getByRole('heading', { name: /claim device/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Intent ID from administrator')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Claim token from administrator')).toBeInTheDocument()
  })

  it('keeps Claim Device disabled until intent id and token are entered', () => {
    renderClaim()
    const submit = screen.getByRole('button', { name: /claim device/i })
    expect(submit).toBeDisabled()
  })

  it('claims a device and provisions the app on success', async () => {
    mocks.fetchImpl.mockResolvedValue(
      new Response(
        JSON.stringify({ device_id: 'dev-9', api_key: 'key-123', site_id: 'site-7' }),
        { status: 200 },
      ),
    )
    renderClaim()
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: /claim device/i }))
    expect(screen.getByText('Claiming...')).toBeInTheDocument()

    await waitFor(() => {
      expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({
        deviceId: 'dev-9',
        apiKey: 'key-123',
        siteId: 'site-7',
        enrollmentMethod: 'pre-provisioned',
      }))
    })
    expect(mocks.setDeviceInfo).toHaveBeenCalledWith(expect.objectContaining({ deviceId: 'dev-9', siteId: 'site-7' }))
    expect(mocks.setIsProvisioned).toHaveBeenCalledWith(true)
  })

  it('uses a generated device name when none is provided', async () => {
    mocks.fetchImpl.mockResolvedValue(
      new Response(
        JSON.stringify({ device_id: 'dev-9', api_key: 'key-123', site_id: 'site-7' }),
        { status: 200 },
      ),
    )
    renderClaim()
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: /claim device/i }))

    await waitFor(() => {
      expect(mocks.save).toHaveBeenCalled()
    })
    expect(mocks.save.mock.calls[0][0].deviceName as string).toMatch(/^Device-/)
  })

  it('shows an error message when the claim fails', async () => {
    mocks.fetchImpl.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Claim token invalid' }), { status: 400 }),
    )
    renderClaim()
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: /claim device/i }))

    await waitFor(() => {
      expect(screen.getByText(/Claim token invalid/i)).toBeInTheDocument()
    })
    expect(mocks.save).not.toHaveBeenCalled()
    expect(mocks.setIsProvisioned).not.toHaveBeenCalled()
  })

  it('displays a generic error for non-authoritative failures', async () => {
    mocks.fetchImpl.mockResolvedValue(new Response('boom', { status: 500 }))
    renderClaim()
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: /claim device/i }))

    await waitFor(() => {
      expect(screen.getByText(/Claim failed/i)).toBeInTheDocument()
    })
  })

  it('navigates back to setup options', () => {
    renderClaim()
    expect(screen.getByRole('button', { name: /back to setup options/i })).toBeInTheDocument()
  })
})
