import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { AxiosError, type AxiosResponse } from 'axios'
import { useAuth } from '@/contexts/AuthContext'
import { AccountSettings } from './AccountSettings'

// ── Mock hooks and contexts ───────────────────────────────────────────────────

const mutate = vi.fn()
const toast = vi.fn()

vi.mock('@/hooks/useUsers', () => ({
  useChangePassword: () => ({ mutate, isPending: false }),
}))

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast }),
}))

const mockUseAuth = vi.mocked(useAuth)

function signInAs(role: 'admin' | 'user') {
  mockUseAuth.mockReturnValue({
    user: { id: 'u2', username: 'j.kowalski', role },
  } as ReturnType<typeof useAuth>)
}

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

function submitButton() {
  return screen.getByRole('button', { name: 'Change Password' }) as HTMLButtonElement
}

beforeEach(() => {
  mutate.mockReset()
  toast.mockReset()
  signInAs('user')
})

afterEach(cleanup)

describe('AccountSettings — profile', () => {
  it('shows the logged-in username and role, read-only', () => {
    render(<AccountSettings />)
    expect(screen.getByText('j.kowalski')).toBeTruthy()
    expect(screen.getByText('User')).toBeTruthy()
    // Only the three password fields are editable.
    expect(document.querySelectorAll('input').length).toBe(3)
  })

  it('shows the Admin role chip for admins', () => {
    signInAs('admin')
    render(<AccountSettings />)
    expect(screen.getByText('Admin')).toBeTruthy()
  })

  it('renders nothing without a logged-in user', () => {
    mockUseAuth.mockReturnValue({ user: null } as ReturnType<typeof useAuth>)
    const { container } = render(<AccountSettings />)
    expect(container.innerHTML).toBe('')
  })
})

describe('AccountSettings — change password', () => {
  it('keeps submit disabled until the form is valid', () => {
    render(<AccountSettings />)
    expect(submitButton().disabled).toBe(true)

    fill('Current password', 'old-secret')
    fill('New password', 'short')
    fill('Confirm new password', 'short')
    expect(screen.getByText('Must be at least 8 characters')).toBeTruthy()
    expect(submitButton().disabled).toBe(true)

    fill('New password', 'new-secret-1')
    fill('Confirm new password', 'new-secret-2')
    expect(screen.getByText('Passwords do not match')).toBeTruthy()
    expect(submitButton().disabled).toBe(true)

    fill('Confirm new password', 'new-secret-1')
    expect(screen.queryByText('Passwords do not match')).toBeNull()
    expect(submitButton().disabled).toBe(false)
    expect(mutate).not.toHaveBeenCalled()
  })

  it('submits current and new password for the logged-in user id', () => {
    render(<AccountSettings />)
    fill('Current password', 'old-secret')
    fill('New password', 'new-secret-1')
    fill('Confirm new password', 'new-secret-1')
    fireEvent.click(submitButton())

    expect(mutate).toHaveBeenCalledTimes(1)
    expect(mutate.mock.calls[0][0]).toEqual({
      id: 'u2',
      data: { new_password: 'new-secret-1', current_password: 'old-secret' },
    })
  })

  it('toasts success and clears the form', () => {
    mutate.mockImplementation((_vars, opts) => opts.onSuccess())
    render(<AccountSettings />)
    fill('Current password', 'old-secret')
    fill('New password', 'new-secret-1')
    fill('Confirm new password', 'new-secret-1')
    fireEvent.click(submitButton())

    expect(toast).toHaveBeenCalledWith('Password changed successfully', 'success')
    expect((screen.getByLabelText('Current password') as HTMLInputElement).value).toBe('')
    expect((screen.getByLabelText('New password') as HTMLInputElement).value).toBe('')
    expect((screen.getByLabelText('Confirm new password') as HTMLInputElement).value).toBe('')
  })

  it('toasts the API error detail and keeps the form values', () => {
    const err = new AxiosError('Request failed with status code 400')
    err.response = { data: { detail: 'Current password is incorrect' } } as AxiosResponse
    mutate.mockImplementation((_vars, opts) => opts.onError(err))
    render(<AccountSettings />)
    fill('Current password', 'wrong')
    fill('New password', 'new-secret-1')
    fill('Confirm new password', 'new-secret-1')
    fireEvent.click(submitButton())

    expect(toast).toHaveBeenCalledWith('Current password is incorrect', 'error')
    expect((screen.getByLabelText('New password') as HTMLInputElement).value).toBe('new-secret-1')
  })

  it('falls back to the error message when there is no API detail', () => {
    mutate.mockImplementation((_vars, opts) => opts.onError(new Error('Network Error')))
    render(<AccountSettings />)
    fill('Current password', 'old-secret')
    fill('New password', 'new-secret-1')
    fill('Confirm new password', 'new-secret-1')
    fireEvent.click(submitButton())

    expect(toast).toHaveBeenCalledWith('Network Error', 'error')
  })
})
