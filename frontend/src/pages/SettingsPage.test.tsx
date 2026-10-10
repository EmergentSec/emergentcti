import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render as rtlRender, screen } from '@testing-library/react'
import { Link, MemoryRouter } from 'react-router-dom'
import type { ReactElement } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import SettingsPage from './SettingsPage'

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}))

vi.mock('@/components/settings/ApiKeyManager', () => ({
  ApiKeyManager: () => <div>ApiKeyManager</div>,
}))

vi.mock('@/components/settings/UserManager', () => ({
  UserManager: () => <div>UserManager</div>,
}))

vi.mock('@/components/settings/AllowlistManager', () => ({
  AllowlistManager: () => <div>AllowlistManager</div>,
}))

vi.mock('@/components/settings/ExportProfileManager', () => ({
  ExportProfileManager: () => <div>ExportProfileManager</div>,
}))

vi.mock('@/components/settings/AccountSettings', () => ({
  AccountSettings: () => <div>AccountSettings</div>,
}))

vi.mock('@/components/settings/GeneralSettings', () => ({
  GeneralSettings: () => <div>GeneralSettings</div>,
}))

const mockUseAuth = vi.mocked(useAuth)

function render(ui: ReactElement) {
  return rtlRender(
    <MemoryRouter initialEntries={[window.location.pathname + window.location.search]}>
      {ui}
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', '/')
})

describe('SettingsPage', () => {
  it('admin sees all 6 tabs and defaults to API keys pane', () => {
    mockUseAuth.mockReturnValue({ isAdmin: true } as ReturnType<typeof useAuth>)

    render(<SettingsPage />)

    expect(screen.getByText('API keys')).toBeTruthy()
    expect(screen.getByText('Members')).toBeTruthy()
    expect(screen.getByText('Allowlist')).toBeTruthy()
    expect(screen.getByText('Export profiles')).toBeTruthy()
    expect(screen.getByText('Account')).toBeTruthy()
    expect(screen.getByText('General')).toBeTruthy()
    expect(screen.getByText('ApiKeyManager')).toBeTruthy()
    expect(screen.queryByText('AccountSettings')).toBeNull()
    expect(screen.queryByText('GeneralSettings')).toBeNull()
    expect(screen.queryByText('UserManager')).toBeNull()
  })

  it('non-admin sees no admin-only tabs and defaults to Account', () => {
    mockUseAuth.mockReturnValue({ isAdmin: false } as ReturnType<typeof useAuth>)

    render(<SettingsPage />)

    expect(screen.queryByText('API keys')).toBeNull()
    expect(screen.queryByText('Members')).toBeNull()
    expect(screen.getByText('Account')).toBeTruthy()
    expect(screen.getByText('General')).toBeTruthy()
    expect(screen.getByText('AccountSettings')).toBeTruthy()
    expect(screen.queryByText('GeneralSettings')).toBeNull()
    expect(screen.queryByText('ApiKeyManager')).toBeNull()

    fireEvent.click(screen.getByText('General'))
    expect(screen.getByText('GeneralSettings')).toBeTruthy()
    expect(screen.queryByText('AccountSettings')).toBeNull()
  })

  it('admin can open the Account tab', () => {
    mockUseAuth.mockReturnValue({ isAdmin: true } as ReturnType<typeof useAuth>)

    render(<SettingsPage />)

    fireEvent.click(screen.getByText('Account'))
    expect(screen.getByText('AccountSettings')).toBeTruthy()
    expect(screen.queryByText('ApiKeyManager')).toBeNull()
  })

  it('switching tab swaps the right pane', () => {
    mockUseAuth.mockReturnValue({ isAdmin: true } as ReturnType<typeof useAuth>)

    render(<SettingsPage />)

    // starts on API keys
    expect(screen.getByText('ApiKeyManager')).toBeTruthy()

    // click General
    fireEvent.click(screen.getByText('General'))
    expect(screen.getByText('GeneralSettings')).toBeTruthy()
    expect(screen.queryByText('ApiKeyManager')).toBeNull()

    // click Members
    fireEvent.click(screen.getByText('Members'))
    expect(screen.getByText('UserManager')).toBeTruthy()
    expect(screen.queryByText('GeneralSettings')).toBeNull()
  })

  it('non-admin can read the Allowlist and Export profiles panes', () => {
    mockUseAuth.mockReturnValue({ isAdmin: false } as ReturnType<typeof useAuth>)

    render(<SettingsPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Allowlist' }))
    expect(screen.getByText('AllowlistManager')).toBeTruthy()
    expect(screen.queryByText('AccountSettings')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Export profiles' }))
    expect(screen.getByText('ExportProfileManager')).toBeTruthy()
    expect(screen.queryByText('AllowlistManager')).toBeNull()
  })

  it('opens the pane named by ?tab= and marks it current', () => {
    mockUseAuth.mockReturnValue({ isAdmin: true } as ReturnType<typeof useAuth>)
    window.history.replaceState(null, '', '/settings?tab=allowlist')

    render(<SettingsPage />)

    expect(screen.getByText('AllowlistManager')).toBeTruthy()
    expect(screen.queryByText('ApiKeyManager')).toBeNull()
    expect(screen.getByRole('button', { name: 'Allowlist' }).getAttribute('aria-current')).toBe('page')
  })

  it('follows a deep link while the Settings page is already mounted', () => {
    mockUseAuth.mockReturnValue({ isAdmin: true } as ReturnType<typeof useAuth>)
    render(
      <>
        <Link to="/settings?tab=allowlist">Manage allowlist</Link>
        <SettingsPage />
      </>,
    )
    expect(screen.getByText('ApiKeyManager')).toBeTruthy()
    fireEvent.click(screen.getByRole('link', { name: 'Manage allowlist' }))
    expect(screen.getByText('AllowlistManager')).toBeTruthy()
    expect(screen.queryByText('ApiKeyManager')).toBeNull()
  })

  it('ignores ?tab= for an admin-only pane when the user is not an admin', () => {
    mockUseAuth.mockReturnValue({ isAdmin: false } as ReturnType<typeof useAuth>)
    window.history.replaceState(null, '', '/settings?tab=apikeys')

    render(<SettingsPage />)

    expect(screen.getByText('AccountSettings')).toBeTruthy()
    expect(screen.queryByText('ApiKeyManager')).toBeNull()
  })
})
