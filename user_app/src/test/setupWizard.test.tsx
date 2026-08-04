import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppProvider } from '../context/AppContext'
import SetupWizard from '../views/SetupWizard'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

function setupFetchMock(available = true) {
  mockFetch.mockImplementation((url: string) => {
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
    const [deviceType] = screen.getAllByRole('combobox')
    expect(deviceType.value).toBe('')
    expect(deviceType.options[0].text).toBe('-')
  })

  it('defaults Operating System to Auto-detect', () => {
    renderSetup()
    const [, deviceOs] = screen.getAllByRole('combobox')
    expect(deviceOs.value).toBe('auto')
    expect(deviceOs.options[0].text).toBe('Auto-detect')
  })

  it('keeps Next disabled until device type is selected', () => {
    renderSetup()
    const next = screen.getByRole('button', { name: /next/i })
    expect(next).toBeDisabled()
    fireEvent.change(screen.getByPlaceholderText('Enter your Site ID'), { target: { value: 'site-001' } })
    fireEvent.change(screen.getByPlaceholderText('e.g. Device-001'), { target: { value: 'Device-001' } })
    expect(next).toBeDisabled()
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'kiosk' } })
    expect(next).toBeDisabled()
    fireEvent.change(screen.getByPlaceholderText('Enter your Bootstrap Key'), { target: { value: 'bk-abc123' } })
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
    fireEvent.change(screen.getByPlaceholderText('e.g. Device-001'), { target: { value: 'Device-001' } })
    expect(await screen.findByText('✓ Name available')).toBeInTheDocument()
  })

  it('blocks Next when the device name is already in use', async () => {
    setupFetchMock(false)
    renderSetup()
    const next = screen.getByRole('button', { name: /next/i })
    fireEvent.change(screen.getByPlaceholderText('Enter your Site ID'), { target: { value: 'site-001' } })
    fireEvent.change(screen.getByPlaceholderText('Enter your Bootstrap Key'), { target: { value: 'bk-abc123' } })
    fireEvent.change(screen.getByPlaceholderText('e.g. Device-001'), { target: { value: 'Device-001' } })
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'kiosk' } })
    expect(next).toBeEnabled()
    expect(await screen.findByText(/already in use/)).toBeInTheDocument()
    expect(next).toBeDisabled()
  })

  it('resolves the auto-detected OS before proceeding', async () => {
    Object.defineProperty(navigator, 'userAgentData', { value: { platform: 'Android' }, configurable: true })
    renderSetup()
    fillRequiredFields()
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(await screen.findByText('Setup Method')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    const [, deviceOs] = screen.getAllByRole('combobox')
    expect(deviceOs.value).toBe('android')
  })
})
