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
  return renderSetupAt('/setup')
}

function renderSetupAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
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

async function proceedToMethod() {
  fillRequiredFields()
  expect(await screen.findByText('✓ Site credentials verified')).toBeInTheDocument()
  expect(await screen.findByText('✓ Name available')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /next/i }))
  expect(await screen.findByText('Setup Method')).toBeInTheDocument()
}

async function proceedToEmulatorReview(profile?: RegExp) {
  await proceedToMethod()
  fireEvent.click(screen.getByRole('button', { name: /launch emulated device/i }))
  fireEvent.click(screen.getByRole('button', { name: /next/i }))
  expect(await screen.findByText('Configure Emulator')).toBeInTheDocument()
  if (profile) fireEvent.click(screen.getByRole('button', { name: profile }))
  fireEvent.click(screen.getByRole('button', { name: /next/i }))
  expect(await screen.findByText('Review Settings')).toBeInTheDocument()
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

describe('SetupWizard Method', () => {
  it('returns direct visits without completed setup data to Step 1', async () => {
    renderSetupAt('/method')
    expect(await screen.findByPlaceholderText('Enter your Site ID')).toBeInTheDocument()
  })

  it('uses verified setup details for a real device without asking for the key again', async () => {
    renderSetup()
    await proceedToMethod()
    const realDevice = screen.getByRole('button', { name: /set up a real device/i })
    expect(realDevice).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('Step 2 of 4')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()
    fireEvent.click(realDevice)
    expect(realDevice).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Step 2 of 3')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(await screen.findByText('Review Settings')).toBeInTheDocument()
    expect(screen.queryByText('Enter bootstrap key')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(await screen.findByText('Setup Method')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /set up a real device/i })).toHaveAttribute('aria-pressed', 'true')
  })

  it('routes emulator selection to emulator configuration', async () => {
    renderSetup()
    await proceedToMethod()
    const emulator = screen.getByRole('button', { name: /launch emulated device/i })
    fireEvent.click(emulator)
    expect(emulator).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Step 2 of 4')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(await screen.findByText('Configure Emulator')).toBeInTheDocument()
  })
})

describe('SetupWizard Emulator Review', () => {
  it('returns direct visits without completed setup data to Step 1', async () => {
    renderSetupAt('/setup/review')
    expect(await screen.findByPlaceholderText('Enter your Site ID')).toBeInTheDocument()
  })

  it('shows the selected emulator identity and blocks launch in browser mode', async () => {
    renderSetup()
    await proceedToEmulatorReview()
    expect(screen.getByRole('link', { name: /Device Setup/ })).toHaveAttribute('href', '/setup')
    expect(screen.getByRole('link', { name: /Method/ })).toHaveAttribute('href', '/method')
    expect(screen.getByRole('link', { name: /Emulator/ })).toHaveAttribute('href', '/emulator')
    expect(screen.getByRole('link', { name: /Complete/ })).toHaveAttribute('href', '/setup/review')
    expect(screen.getByText('Emulator Profile')).toBeInTheDocument()
    expect(screen.getByText('Linux POS')).toBeInTheDocument()
    expect(screen.getByText(/Pos Terminal/i)).toBeInTheDocument()
    expect(screen.getByText('Linux 6.8.0 (Debian 12)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Launch Emulator' })).toBeDisabled()
    expect(screen.getByText(/requires the Electron desktop app/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(await screen.findByText('Configure Emulator')).toBeInTheDocument()
  })

  it('navigates to reached setup pages from the progress links', async () => {
    renderSetup()
    await proceedToEmulatorReview()
    fireEvent.click(screen.getByRole('link', { name: /Method/ }))
    expect(await screen.findByText('Setup Method')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /launch emulated device/i })).toHaveAttribute('aria-pressed', 'true')
  })

  it('launches the selected emulator through Electron with verified setup details', async () => {
    const start = vi.fn().mockResolvedValue({ deviceId: 'pos-001', apiKey: 'api-key-001' })
    window.electronAPI = {
      emulator: { start },
    } as unknown as NonNullable<Window['electronAPI']>
    renderSetup()
    await proceedToEmulatorReview()
    const launch = screen.getByRole('button', { name: 'Launch Emulator' })
    expect(launch).toBeEnabled()
    fireEvent.click(launch)
    await vi.waitFor(() => {
      expect(start).toHaveBeenCalledWith(expect.objectContaining({
        emulatorType: 'linux_pos',
        siteId: 'site-001',
        bootstrapKey: 'bk-abc123',
        deviceName: 'Device-001',
        deviceType: 'pos_terminal',
      }))
    })
  })

  it('shows Android identity when the Android POS profile is selected', async () => {
    renderSetup()
    await proceedToEmulatorReview(/Android POS/i)
    expect(screen.getByText('Android POS')).toBeInTheDocument()
    expect(screen.getByText(/Pos Terminal/i)).toBeInTheDocument()
    expect(screen.getByText('Android 14')).toBeInTheDocument()
  })
})
