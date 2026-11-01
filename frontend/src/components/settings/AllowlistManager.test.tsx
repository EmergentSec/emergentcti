import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { AxiosError, type AxiosResponse } from 'axios'
import { AllowlistManager } from './AllowlistManager'
import type { AllowlistEntry } from '@/types/allowlist'

// ── Mock hooks and contexts ───────────────────────────────────────────────────

const ENTRIES: AllowlistEntry[] = [
  {
    id: 'al-1',
    kind: 'exact',
    value: '8.8.8.8',
    observable_type: 'ip-addr',
    reason: 'Public DNS resolver',
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
  },
  {
    id: 'al-2',
    kind: 'domain_suffix',
    value: 'example.com',
    observable_type: 'domain-name',
    reason: 'Corporate domain',
    created_at: '2026-10-02T00:00:00Z',
    updated_at: '2026-10-02T00:00:00Z',
  },
]

const mockUseAllowlist = vi.fn()
const mockCreate = vi.fn()
const mockDelete = vi.fn()
const mockToast = vi.fn()
const { mockAuth, mockConfig } = vi.hoisted(() => ({
  mockAuth: { isAdmin: true },
  mockConfig: { data: { observable_retention_days: 180 } as { observable_retention_days: number } | undefined },
}))

vi.mock('@/hooks/useAllowlist', () => ({
  useAllowlist: () => mockUseAllowlist(),
  useCreateAllowlistEntry: () => ({ mutate: mockCreate, isPending: false }),
  useDeleteAllowlistEntry: () => ({ mutate: mockDelete, isPending: false }),
}))

vi.mock('@/hooks/useConfig', () => ({
  useConfig: () => mockConfig,
}))

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: mockToast }),
}))

function httpError(status: number, detail: unknown) {
  return new AxiosError('Request failed', String(status), undefined, undefined, {
    status,
    data: { detail },
  } as AxiosResponse)
}

function renderLoaded(entries: AllowlistEntry[] = ENTRIES) {
  mockUseAllowlist.mockReturnValue({ data: entries, isLoading: false, error: null })
  return render(<AllowlistManager />)
}

function fillAndSubmit({ kind, type, value, reason }: { kind?: string; type?: string; value: string; reason: string }) {
  fireEvent.click(screen.getByRole('button', { name: 'Add entry' }))
  if (kind) fireEvent.change(screen.getByLabelText('Match kind'), { target: { value: kind } })
  if (type) fireEvent.change(screen.getByLabelText('Observable type'), { target: { value: type } })
  fireEvent.change(screen.getByLabelText('Value'), { target: { value } })
  fireEvent.change(screen.getByLabelText('Reason'), { target: { value: reason } })
  fireEvent.click(screen.getByRole('button', { name: 'Add to allowlist' }))
}

afterEach(() => {
  cleanup()
  mockAuth.isAdmin = true
  mockConfig.data = { observable_retention_days: 180 }
  mockCreate.mockReset()
  mockDelete.mockReset()
  mockToast.mockReset()
})

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('AllowlistManager — reading', () => {
  it('lists entries with kind, value, type and reason', () => {
    renderLoaded()
    const row = screen.getByText('8.8.8.8').closest('tr')!
    expect(within(row).getByText('Exact value')).toBeTruthy()
    expect(within(row).getByText('IP Address')).toBeTruthy()
    expect(within(row).getByText('Public DNS resolver')).toBeTruthy()

    const suffixRow = screen.getByText('example.com').closest('tr')!
    expect(within(suffixRow).getByText('Domain suffix')).toBeTruthy()
    expect(within(suffixRow).getByText('Domain')).toBeTruthy()
  })

  it('explains reversible allowlisting versus irreversible retention with the configured period', () => {
    renderLoaded()
    expect(screen.getByRole('heading', { name: 'Allowlisting is reversible' })).toBeTruthy()
    expect(
      screen.getByText(
        /Removing an entry puts its\s+matches back into exports immediately — but only for observables that retention has\s+not already deleted/,
      ),
    ).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Retention deletion is irreversible' })).toBeTruthy()
    expect(screen.getByText(/A daily job permanently deletes observables not seen for more than 180 days/)).toBeTruthy()
    expect(screen.getByText(/allowlisting does not protect an observable from\s+retention/)).toBeTruthy()
  })

  it('says retention is disabled when configured as 0', () => {
    mockConfig.data = { observable_retention_days: 0 }
    renderLoaded()
    expect(screen.getByText(/Retention is currently disabled on this instance/)).toBeTruthy()
  })

  it('shows an empty state', () => {
    renderLoaded([])
    expect(screen.getByText(/No allowlist entries/)).toBeTruthy()
  })

  it('shows a load error', () => {
    mockUseAllowlist.mockReturnValue({ data: undefined, isLoading: false, error: new Error('boom') })
    render(<AllowlistManager />)
    expect(screen.getByRole('alert').textContent).toBe('Failed to load the allowlist')
  })

  it('non-admin can read entries but gets no mutation controls', () => {
    mockAuth.isAdmin = false
    renderLoaded()
    expect(screen.getByText('8.8.8.8')).toBeTruthy()
    expect(screen.getByText('Only administrators can add or remove allowlist entries.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Add entry' })).toBeNull()
    expect(screen.queryByRole('button', { name: /remove/i })).toBeNull()
  })
})

describe('AllowlistManager — creating', () => {
  it('preserves literal exact values while trimming the reason', () => {
    renderLoaded()
    fillAndSubmit({ type: 'file-hash', value: '  abc123  ', reason: '  Internal tool  ' })

    expect(mockCreate.mock.calls[0][0]).toEqual({
      kind: 'exact',
      value: '  abc123  ',
      observable_type: 'file-hash',
      reason: 'Internal tool',
    })

    act(() => mockCreate.mock.calls[0][1].onSuccess())
    expect(mockToast).toHaveBeenCalledWith('Allowlist entry added', 'success')
    expect(screen.queryByLabelText('Value')).toBeNull()
  })

  it('creates a CIDR entry pinned to IP addresses', () => {
    renderLoaded()
    fillAndSubmit({ kind: 'cidr', value: '10.0.0.0/8', reason: 'RFC1918' })

    expect((screen.getByLabelText('Observable type') as HTMLSelectElement).disabled).toBe(true)
    expect(mockCreate.mock.calls[0][0]).toEqual({
      kind: 'cidr',
      value: '10.0.0.0/8',
      observable_type: 'ip-addr',
      reason: 'RFC1918',
    })
  })

  it('creates a domain suffix entry pinned to domains', () => {
    renderLoaded()
    fillAndSubmit({ kind: 'domain_suffix', value: 'example.org', reason: 'Ours' })

    expect(screen.getByText(/does not match URLs or email addresses/)).toBeTruthy()
    expect(mockCreate.mock.calls[0][0]).toEqual({
      kind: 'domain_suffix',
      value: 'example.org',
      observable_type: 'domain-name',
      reason: 'Ours',
    })
  })

  it('blocks submission and shows field errors when the form is incomplete', () => {
    renderLoaded()
    fillAndSubmit({ value: '', reason: '' })

    expect(screen.getByText('Value is required')).toBeTruthy()
    expect(screen.getByText('Reason is required')).toBeTruthy()
    expect(screen.getByText('Choose the observable type this value applies to')).toBeTruthy()
    expect(screen.getByLabelText('Value').getAttribute('aria-invalid')).toBe('true')
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('blocks an invalid CIDR range', () => {
    renderLoaded()
    fillAndSubmit({ kind: 'cidr', value: '10.0.0.0/40', reason: 'x' })
    expect(screen.getByText('IPv4 prefix length must be between 0 and 32')).toBeTruthy()
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('reports a duplicate (409) inline and keeps the form open', () => {
    renderLoaded()
    fillAndSubmit({ type: 'ip-addr', value: '8.8.8.8', reason: 'again' })

    act(() => mockCreate.mock.calls[0][1].onError(httpError(409, 'Allowlist entry already exists')))
    expect(screen.getByRole('alert').textContent).toBe('This entry is already on the allowlist.')
    expect(mockToast).toHaveBeenCalledWith('This entry is already on the allowlist.', 'error')
    expect((screen.getByLabelText('Value') as HTMLInputElement).value).toBe('8.8.8.8')
  })

  it('surfaces the server validation message for other errors', () => {
    renderLoaded()
    fillAndSubmit({ type: 'ip-addr', value: 'not-an-ip', reason: 'x' })

    act(() => mockCreate.mock.calls[0][1].onError(httpError(422, [{ msg: 'Invalid IP address' }])))
    expect(screen.getByRole('alert').textContent).toBe('Invalid IP address')
  })

  it('falls back to a generic message when the error has no detail', () => {
    renderLoaded()
    fillAndSubmit({ type: 'ip-addr', value: '1.1.1.1', reason: 'x' })

    act(() => mockCreate.mock.calls[0][1].onError(new Error('Network Error')))
    expect(screen.getByRole('alert').textContent).toBe('Failed to add allowlist entry')
  })
})

describe('AllowlistManager — removing', () => {
  it('confirms before deleting and explains the effect', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'Remove 8.8.8.8 from the allowlist' }))
    expect(mockDelete).not.toHaveBeenCalled()
    expect(screen.getByText(/included in exports\s+again immediately/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Remove entry' }))
    expect(mockDelete.mock.calls[0][0]).toBe('al-1')

    act(() => mockDelete.mock.calls[0][1].onSuccess())
    expect(mockToast).toHaveBeenCalledWith('8.8.8.8 removed from the allowlist', 'success')
    expect(screen.queryByRole('button', { name: 'Remove entry' })).toBeNull()
  })

  it('can be cancelled', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'Remove 8.8.8.8 from the allowlist' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(mockDelete).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Remove entry' })).toBeNull()
  })

  it('reports a failed delete', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'Remove 8.8.8.8 from the allowlist' }))
    fireEvent.click(screen.getByRole('button', { name: 'Remove entry' }))

    act(() => mockDelete.mock.calls[0][1].onError(httpError(403, 'Admin access required')))
    expect(mockToast).toHaveBeenCalledWith('Admin access required', 'error')
  })
})
