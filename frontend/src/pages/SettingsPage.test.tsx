import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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

vi.mock('@/components/settings/GeneralSettings', () => ({
  GeneralSettings: () => <div>GeneralSettings</div>,
}))

const mockUseAuth = vi.mocked(useAuth)

afterEach(cleanup)

describe('SettingsPage', () => {
  it('admin sees all 3 tabs and defaults to API keys pane', () => {
    mockUseAuth.mockReturnValue({ isAdmin: true } as ReturnType<typeof useAuth>)

    render(<SettingsPage />)

    expect(screen.getByText('API keys')).toBeTruthy()
    expect(screen.getByText('Members')).toBeTruthy()
    expect(screen.getByText('General')).toBeTruthy()
    expect(screen.getByText('ApiKeyManager')).toBeTruthy()
    expect(screen.queryByText('GeneralSettings')).toBeNull()
    expect(screen.queryByText('UserManager')).toBeNull()
  })

  it('non-admin sees only General tab and defaults to it', () => {
    mockUseAuth.mockReturnValue({ isAdmin: false } as ReturnType<typeof useAuth>)

    render(<SettingsPage />)

    expect(screen.queryByText('API keys')).toBeNull()
    expect(screen.queryByText('Members')).toBeNull()
    expect(screen.getByText('General')).toBeTruthy()
    expect(screen.getByText('GeneralSettings')).toBeTruthy()
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
})
