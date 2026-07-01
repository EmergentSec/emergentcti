import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { UserManager } from './UserManager'

// ── Mock hooks and contexts ───────────────────────────────────────────────────

const mockUsers = [
  {
    id: 'u1',
    username: 'a.reyes',
    email: 'a.reyes@acme-soc.io',
    role: 'admin' as const,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    last_login_at: '2026-06-29T12:00:00Z',
  },
  {
    id: 'u2',
    username: 'j.kowalski',
    email: 'j.kowalski@acme-soc.io',
    role: 'user' as const,
    is_active: true,
    created_at: '2026-02-01T00:00:00Z',
    last_login_at: null,
  },
]

vi.mock('@/hooks/useUsers', () => ({
  useUsers: () => ({ data: mockUsers, isLoading: false, error: null }),
  useCreateUser: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateUser: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteUser: () => ({ mutate: vi.fn(), isPending: false }),
  useChangePassword: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ user: { id: 'u1', username: 'a.reyes', role: 'admin' } }),
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

vi.mock('@/components/ui/Dialog', () => ({
  Dialog: ({
    open,
    children,
    title,
  }: {
    open: boolean
    children: React.ReactNode
    title?: string
  }) =>
    open ? (
      <div data-testid="dialog" aria-label={title}>
        {children}
      </div>
    ) : null,
}))

afterEach(cleanup)

describe('UserManager — member list', () => {
  it('renders username and email for each member', () => {
    render(<UserManager />)
    expect(screen.getByText('a.reyes')).toBeTruthy()
    expect(screen.getByText('a.reyes@acme-soc.io')).toBeTruthy()
    expect(screen.getByText('j.kowalski')).toBeTruthy()
    expect(screen.getByText('j.kowalski@acme-soc.io')).toBeTruthy()
  })

  it('renders "Admin" role chip for admin users', () => {
    render(<UserManager />)
    expect(screen.getByText('Admin')).toBeTruthy()
  })

  it('renders "User" role chip for non-admin users (not "Analyst" or "Read-only")', () => {
    render(<UserManager />)
    expect(screen.getByText('User')).toBeTruthy()
    expect(screen.queryByText(/analyst/i)).toBeNull()
    expect(screen.queryByText(/read-only/i)).toBeNull()
  })

  it('shows "Never" for a member with no last_login_at', () => {
    render(<UserManager />)
    expect(screen.getByText('Never')).toBeTruthy()
  })

  it('renders the page header and subtitle', () => {
    render(<UserManager />)
    expect(screen.getByText('Members')).toBeTruthy()
    expect(screen.getByText(/manage who can access this instance/i)).toBeTruthy()
  })

  it('renders the Invite button', () => {
    render(<UserManager />)
    expect(screen.getByRole('button', { name: /invite/i })).toBeTruthy()
  })
})
