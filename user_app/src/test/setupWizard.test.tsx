import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppProvider } from '../context/AppContext'
import SetupWizard from '../views/SetupWizard'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

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
