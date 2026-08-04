import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppProvider } from '../context/AppContext'
import SetupWizard from '../views/SetupWizard'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

function setupFetchMock(available = true) {
  mockFetch.mockImplementation((url: string) => {
    if (String(url).includes('/verify-bootstrap')) {
      return Promise.resolve(
        new Response(JSON.stringify({ data: { verified: true } }), { status: 200 }),
      )
    }
    if (String(url).includes('/check-name')) {
      return Promise.resolve(
        new Response(JSON.stringify({ data: { available } }), { status: 200 }),
      )
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
  })
}

function renderSetup() {
  return render(
    <MemoryRouter initialEntries={['/setup']}>
      <AppProvider>
        <SetupWizard />
      </AppProvider>
    </MemoryRouter>,
  )
}

function fillRequiredFields() {
  fireEvent.change(screen.getByPlaceholderText('Enter your Site ID'), { target: { value: 'site-001' } })
  fireEvent.change(screen.getByPlaceholderText('Enter your Bootstrap Key'), { target: { value: 'bk-abc123' } })
  fireEvent.change(screen.getByPlaceholderText('e.g. Device-001'), { target: { value: 'Device-001' } })
  fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'kiosk' } })
}

afterEach(() => {
  delete (navigator as { userAgentData?: unknown }).userAgentData
  delete window.electronAPI
})

beforeEach(() => {
  mockFetch.mockReset()
  setupFetchMock(true)
})

describe('SetupWizard Step 1', () => {
  it('renders Device Name label with a consistent example placeholder', () => {
    renderSetup()
    expect(screen.getByText('Device Name')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. Device-001')).toBeInTheDocument()
    expect(screen.queryByText('Hostname')).not.toBeInTheDocument()
  })

  it('shows a neutral "-" option first in Device Type', () => {
    renderSetup()
    const [deviceType] = screen.getAllByRole('combobox') as HTMLSelectElement[]
    expect(deviceType.value).toBe('')
    expect(deviceType.options[0].text).toBe('-')
  })

  it('defaults Operating System to Auto-detect', () => {
    renderSetup()
    const [, deviceOs] = screen.getAllByRole('combobox') as HTMLSelectElement[]
    expect(deviceOs.value).toBe('auto')
    expect(deviceOs.options[0].text).toBe('Auto-detect')
  })

  it('keeps Next disabled until credentials and name are verified', async () => {
    renderSetup()
    const next = screen.getByRole('button', { name: /next/i })
    expect(next).toBeDisabled()
    fireEvent.change(screen.getByPlaceholderText('Enter your Site ID'), { target: { value: 'site-001' } })
    expect(screen.getByText(/enter the bootstrap key provided/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. Device-001')).toBeDisabled()
    fireEvent.change(screen.getByPlaceholderText('Enter your Bootstrap Key'), { target: { value: 'bk-abc123' } })
    expect(next).toBeDisabled()
    expect(await screen.findByText('✓ Site credentials verified')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. Device-001')).toBeEnabled()
    fireEvent.change(screen.getByPlaceholderText('e.g. Device-001'), { target: { value: 'Device-001' } })
    expect(next).toBeDisabled()
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'kiosk' } })
    expect(next).toBeDisabled()
    expect(await screen.findByText('✓ Name available')).toBeInTheDocument()
    expect(next).toBeEnabled()
  })

  it('shows the dev key hint for emulator testing', () => {
    renderSetup()
    expect(screen.getByText(/homepot-dev-emulator-key/)).toBeInTheDocument()
  })

  it('shows name availability feedback', async () => {
    renderSetup()
    fireEvent.change(screen.getByPlaceholderText('Enter your Site ID'), { target: { value: 'site-001' } })
    fireEvent.change(screen.getByPlaceholderText('Enter your Bootstrap Key'), { target: { value: 'bk-abc123' } })
    expect(await screen.findByText('✓ Site credentials verified')).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('e.g. Device-001'), { target: { value: 'Device-001' } })
    expect(await screen.findByText('✓ Name available')).toBeInTheDocument()
  })

  it('blocks Next when the device name is already in use', async () => {
    setupFetchMock(false)
    renderSetup()
    const next = screen.getByRole('button', { name: /next/i })
    fireEvent.change(screen.getByPlaceholderText('Enter your Site ID'), { target: { value: 'site-001' } })
    fireEvent.change(screen.getByPlaceholderText('Enter your Bootstrap Key'), { target: { value: 'bk-abc123' } })
    expect(await screen.findByText('✓ Site credentials verified')).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('e.g. Device-001'), { target: { value: 'Device-001' } })
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'kiosk' } })
    expect(next).toBeDisabled()
    expect(await screen.findByText(/already in use/)).toBeInTheDocument()
    expect(next).toBeDisabled()
  })

  it('keeps the name locked when site credentials are invalid', async () => {
    mockFetch.mockImplementation((url: string) => {
      if (String(url).includes('/verify-bootstrap')) {
        return Promise.resolve(
          new Response(JSON.stringify({ data: { verified: false } }), { status: 200 }),
        )
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
    })
    renderSetup()
    fireEvent.change(screen.getByPlaceholderText('Enter your Site ID'), { target: { value: 'site-001' } })
    fireEvent.change(screen.getByPlaceholderText('Enter your Bootstrap Key'), { target: { value: 'wrong-key' } })
    expect(await screen.findByText(/Site ID or bootstrap key is incorrect/)).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. Device-001')).toBeDisabled()
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()
  })

  it('clears downstream verification when site credentials change', async () => {
    renderSetup()
    fillRequiredFields()
    expect(await screen.findByText('✓ Site credentials verified')).toBeInTheDocument()
    expect(await screen.findByText('✓ Name available')).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('Enter your Site ID'), { target: { value: 'site-002' } })
    expect(screen.queryByText('✓ Site credentials verified')).not.toBeInTheDocument()
    expect(screen.queryByText('✓ Name available')).not.toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. Device-001')).toBeDisabled()
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()
  })

  it('resolves the auto-detected OS before proceeding', async () => {
    Object.defineProperty(navigator, 'userAgentData', { value: { platform: 'Android' }, configurable: true })
    renderSetup()
    fireEvent.change(screen.getByPlaceholderText('Enter your Site ID'), { target: { value: 'site-001' } })
    fireEvent.change(screen.getByPlaceholderText('Enter your Bootstrap Key'), { target: { value: 'bk-abc123' } })
    expect(await screen.findByText('✓ Site credentials verified')).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('e.g. Device-001'), { target: { value: 'Device-001' } })
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'kiosk' } })
    expect(await screen.findByText('✓ Name available')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(await screen.findByText('Setup Method')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    const [, deviceOs] = screen.getAllByRole('combobox') as HTMLSelectElement[]
    expect(deviceOs.value).toBe('android')
  })

  it('prefers the native Electron OS over browser detection', async () => {
    Object.defineProperty(navigator, 'userAgentData', { value: { platform: 'Windows' }, configurable: true })
    window.electronAPI = {
      device: {
        dna: vi.fn().mockResolvedValue({
          hostname: 'device-001',
          platform: 'linux',
          release: '6.8.0',
          mac: '00:00:00:00:00:00',
          ip: '127.0.0.1',
        }),
      },
    } as unknown as NonNullable<Window['electronAPI']>
    renderSetup()
    fireEvent.change(screen.getByPlaceholderText('Enter your Site ID'), { target: { value: 'site-001' } })
    fireEvent.change(screen.getByPlaceholderText('Enter your Bootstrap Key'), { target: { value: 'bk-abc123' } })
    expect(await screen.findByText('✓ Site credentials verified')).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('e.g. Device-001'), { target: { value: 'Device-001' } })
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'kiosk' } })
    expect(await screen.findByText('✓ Name available')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(await screen.findByText('Setup Method')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    const [, deviceOs] = screen.getAllByRole('combobox') as HTMLSelectElement[]
    expect(deviceOs.value).toBe('linux')
  })
})
