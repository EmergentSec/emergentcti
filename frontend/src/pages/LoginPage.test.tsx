import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import LoginPage from './LoginPage'

const login = vi.fn()
const toast = vi.fn()

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ login }),
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast }),
}))

beforeEach(() => {
  login.mockReset()
  toast.mockReset()
})

afterEach(cleanup)

describe('LoginPage', () => {
  it('renders labelled username and password fields', () => {
    render(<LoginPage />)
    expect(screen.getByLabelText('Username')).toBeTruthy()
    expect(screen.getByLabelText('Password')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeTruthy()
  })

  it('keeps submit disabled until both fields are filled', () => {
    render(<LoginPage />)
    const submit = screen.getByRole('button', { name: 'Sign In' }) as HTMLButtonElement
    expect(submit.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'admin' } })
    expect(submit.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret' } })
    expect(submit.disabled).toBe(false)
  })

  it('trims the username and submits credentials', async () => {
    login.mockResolvedValue(true)
    render(<LoginPage />)
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: '  admin  ' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    await waitFor(() => expect(login).toHaveBeenCalledWith({ username: 'admin', password: 'secret' }))
  })

  it('announces invalid credentials as an alert', async () => {
    login.mockResolvedValue(false)
    render(<LoginPage />)
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'admin' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Invalid username or password')
    expect(toast).toHaveBeenCalledWith('Invalid credentials', 'error')
  })
})
