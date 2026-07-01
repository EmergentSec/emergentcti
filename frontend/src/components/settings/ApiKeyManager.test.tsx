import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { ApiKeyManager } from './ApiKeyManager'

// ── Mock react-query (component calls useQuery/useMutation directly) ──────────

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn().mockReturnValue({
    data: [
      {
        id: 'key-1',
        name: 'Production SIEM',
        key_prefix: 'cti_8f2ad91c',
        is_active: true,
        created_at: '2026-04-02T10:00:00Z',
        last_used_at: '2026-04-10T08:30:00Z',
        description: null,
      },
      {
        id: 'key-2',
        name: 'Default Admin Key',
        key_prefix: 'cti_AB12CD34',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        last_used_at: null,
        description: null,
      },
    ],
    isLoading: false,
    error: null,
  }),
  useMutation: vi.fn().mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  }),
  useQueryClient: vi.fn().mockReturnValue({
    invalidateQueries: vi.fn(),
  }),
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

describe('ApiKeyManager — curl example', () => {
  it('renders the curl example using the X-API-Key header', () => {
    render(<ApiKeyManager />)
    // The <pre> element contains the full curl command (more specific than the subtitle <code>)
    const pre = screen.getByText(/curl -H "X-API-Key:/)
    expect(pre).toBeTruthy()
    expect(pre.textContent).toContain('X-API-Key')
  })

  it('uses the cti_ prefix in the curl example (not ec_live_)', () => {
    render(<ApiKeyManager />)
    const pre = screen.getByText(/curl -H "X-API-Key:/)
    expect(pre.textContent).toContain('cti_')
    expect(pre.textContent).not.toContain('ec_live_')
  })
})

describe('ApiKeyManager — keys table', () => {
  it('renders a key name and its masked prefix in mono', () => {
    render(<ApiKeyManager />)
    expect(screen.getByText('Production SIEM')).toBeTruthy()
    expect(screen.getByText('cti_8f2ad91c')).toBeTruthy()
  })

  it('does NOT render a Role column header', () => {
    render(<ApiKeyManager />)
    // ApiKey has no role field — no ROLE column header or role badge should appear
    expect(screen.queryByText(/^ROLE$/)).toBeNull()
    expect(screen.queryByText(/read-only/i)).toBeNull()
    // Confirm there is no badge/chip labelled "Admin" or "User"
    // (the word "Admin" appears in "Default Admin Key" name but not as a standalone badge)
    const badges = document
      .querySelectorAll('.rounded-full')
    const badgeTexts = Array.from(badges).map((b) => b.textContent?.trim())
    expect(badgeTexts).not.toContain('Admin')
    expect(badgeTexts).not.toContain('User')
  })

  it('shows auto-generated hint for Default Admin Key', () => {
    render(<ApiKeyManager />)
    expect(screen.getByText(/auto-generated on first startup/i)).toBeTruthy()
  })

  it('shows Never for a key with no last_used_at', () => {
    render(<ApiKeyManager />)
    expect(screen.getByText('Never')).toBeTruthy()
  })
})
