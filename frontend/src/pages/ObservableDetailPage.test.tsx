import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen, fireEvent } from '@testing-library/react'
import { AxiosError, type AxiosResponse } from 'axios'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ObservableDetailPage from './ObservableDetailPage'

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockUseObservable = vi.fn()
const mockUseConfig = vi.fn()

vi.mock('@/hooks/useObservables', () => ({
  useObservable: (id: string | null) => mockUseObservable(id),
}))

vi.mock('@/hooks/useConfig', () => ({
  useConfig: () => mockUseConfig(),
}))

const mockCreateEntry = vi.fn()
const mockToast = vi.fn()
const { mockAuth } = vi.hoisted(() => ({ mockAuth: { isAdmin: true } }))

vi.mock('@/hooks/useAllowlist', () => ({
  useCreateAllowlistEntry: () => ({ mutate: mockCreateEntry, isPending: false }),
}))

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: mockToast }),
}))

// ── Fixtures ─────────────────────────────────────────────────────────────────

const MOCK_OBS = {
  id: 'obs-abc-123',
  type: 'ip-addr' as const,
  value: '5.188.206.18',
  confidence_score: 38,
  first_seen: '2026-05-20T00:00:00Z',
  last_seen: '2026-06-24T00:00:00Z',
  source_count: 1,
  sources: [],
  allowlisted: false,
  allowlist_entry_ids: [] as string[],
  created_at: '',
  updated_at: '',
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function renderWithRoute(id = 'obs-abc-123') {
  return render(
    <MemoryRouter initialEntries={[`/observables/${id}`]}>
      <Routes>
        <Route path="/observables/:id" element={<ObservableDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  mockAuth.isAdmin = true
  mockCreateEntry.mockReset()
  mockToast.mockReset()
})

// Default config mock — overridden in individual tests as needed
const MOCK_CONFIG = {
  confidence_decay_enabled: true,
  confidence_decay_days: 30,
  confidence_decay_rate: 5,
  confidence_decay_floor: 10,
  confidence_decay_interval_hours: 24,
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('ObservableDetailPage', () => {
  it('renders the observable value in mono text', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    mockUseConfig.mockReturnValue({ data: MOCK_CONFIG })
    renderWithRoute()
    expect(screen.getByText('5.188.206.18')).toBeTruthy()
  })

  it('renders the confidence band chip', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    mockUseConfig.mockReturnValue({ data: MOCK_CONFIG })
    renderWithRoute()
    // score 38 → Low band
    expect(screen.getByText('Low confidence')).toBeTruthy()
  })

  it('renders key-facts strip with source count and feeds reporting label', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    mockUseConfig.mockReturnValue({ data: MOCK_CONFIG })
    renderWithRoute()
    // source_count = 1
    expect(screen.getByText('1')).toBeTruthy()
    expect(screen.getByText('feeds reporting')).toBeTruthy()
  })

  // ── Allowlist status + action ───────────────────────────────────────────────

  function renderLoaded(overrides: Partial<typeof MOCK_OBS> = {}) {
    mockUseObservable.mockReturnValue({
      data: { ...MOCK_OBS, ...overrides },
      isLoading: false,
      error: null,
    })
    mockUseConfig.mockReturnValue({ data: MOCK_CONFIG })
    return renderWithRoute()
  }

  it('no longer renders the disabled Block button', () => {
    renderLoaded()
    expect(screen.queryByRole('button', { name: /block/i })).toBeNull()
  })

  it('hides the Allowlist action from non-admin users', () => {
    mockAuth.isAdmin = false
    renderLoaded()
    expect(screen.queryByRole('button', { name: 'Allowlist' })).toBeNull()
    expect(screen.queryByText('Allowlisted')).toBeNull()
  })

  it('shows the Allowlisted badge to every user and replaces the action with a Settings link', () => {
    mockAuth.isAdmin = false
    renderLoaded({ allowlisted: true, allowlist_entry_ids: ['al-1'] })
    expect(screen.getByText('Allowlisted')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Allowlist' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Manage allowlist' }).getAttribute('href')).toBe(
      '/settings?tab=allowlist',
    )
  })

  it('requires a reason before allowlisting', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'Allowlist' }))
    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add to allowlist' }))
    expect(screen.getByRole('alert').textContent).toBe('Reason is required')
    expect(mockCreateEntry).not.toHaveBeenCalled()
  })

  it('admin allowlists the exact typed value with a trimmed reason', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'Allowlist' }))
    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: '  Corporate proxy ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add to allowlist' }))

    expect(mockCreateEntry).toHaveBeenCalledTimes(1)
    expect(mockCreateEntry.mock.calls[0][0]).toEqual({
      kind: 'exact',
      value: '5.188.206.18',
      observable_type: 'ip-addr',
      reason: 'Corporate proxy',
    })

    // Success closes the dialog and confirms via toast
    act(() => mockCreateEntry.mock.calls[0][1].onSuccess())
    expect(screen.queryByLabelText('Reason')).toBeNull()
    expect(mockToast).toHaveBeenCalledWith('5.188.206.18 added to the allowlist', 'success')
  })

  it('creates a CIDR policy for a range-valued IP instead of an invalid exact rule', () => {
    renderLoaded({ value: '192.0.2.0/24' })
    fireEvent.click(screen.getByRole('button', { name: 'Allowlist' }))
    expect(screen.getByText(/also suppresses other IP indicators overlapping this range/)).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Corporate network' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add to allowlist' }))
    expect(mockCreateEntry.mock.calls[0][0]).toEqual({
      kind: 'cidr',
      value: '192.0.2.0/24',
      observable_type: 'ip-addr',
      reason: 'Corporate network',
    })
  })

  it('keeps the dialog open and explains a duplicate (409) entry', () => {
    renderLoaded()
    fireEvent.click(screen.getByRole('button', { name: 'Allowlist' }))
    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Known good' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add to allowlist' }))

    act(() =>
      mockCreateEntry.mock.calls[0][1].onError(
        new AxiosError('Conflict', '409', undefined, undefined, {
          status: 409,
          data: { detail: 'Allowlist entry already exists' },
        } as AxiosResponse),
      ),
    )
    expect(screen.getByRole('alert').textContent).toBe('This value is already on the allowlist.')
    expect(screen.getByLabelText('Reason')).toBeTruthy()
    expect(mockToast).toHaveBeenCalledWith('This value is already on the allowlist.', 'error')
  })

  it('shows a loading spinner while data is loading', () => {
    mockUseObservable.mockReturnValue({ data: undefined, isLoading: true, error: null })
    mockUseConfig.mockReturnValue({ data: undefined })
    renderWithRoute()
    expect(screen.getByRole('status')).toBeTruthy() // LoadingSpinner aria-label="Loading"
    expect(screen.queryByText('5.188.206.18')).toBeNull()
  })

  it('renders the "Low band" label in key-facts confidence cell', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    mockUseConfig.mockReturnValue({ data: MOCK_CONFIG })
    renderWithRoute()
    expect(screen.getByText('Low band')).toBeTruthy()
  })

  it('passes the observable id from the route to useObservable', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    mockUseConfig.mockReturnValue({ data: MOCK_CONFIG })
    renderWithRoute('obs-abc-123')
    expect(mockUseObservable).toHaveBeenCalledWith('obs-abc-123')
  })

  // ── Decay viz section ───────────────────────────────────────────────────────

  it('renders the Effective confidence ring card heading', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    mockUseConfig.mockReturnValue({ data: MOCK_CONFIG })
    renderWithRoute()
    expect(screen.getByText('Effective confidence')).toBeTruthy()
  })

  it('renders the Confidence decay chart heading', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    mockUseConfig.mockReturnValue({ data: MOCK_CONFIG })
    renderWithRoute()
    expect(screen.getByText('Confidence decay')).toBeTruthy()
  })

  it('falls back to decay defaults when config is undefined', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    mockUseConfig.mockReturnValue({ data: undefined })
    renderWithRoute()
    // Default rate=5 → caption "−5/wk after 30d"
    expect(screen.getByTestId('decay-caption').textContent).toContain('−5/wk after 30d')
  })

  // ── Tabs section ────────────────────────────────────────────────────────────

  it('renders Sources tab by default and shows "Manually added" empty state', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    mockUseConfig.mockReturnValue({ data: MOCK_CONFIG })
    renderWithRoute()
    expect(screen.getByRole('tab', { name: 'Sources' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Raw JSON' })).toBeTruthy()
    // MOCK_OBS has no sources → empty state
    expect(screen.getByText('Manually added — no feed sources')).toBeTruthy()
  })

  it('switches to Raw JSON tab and shows GET label and JSON', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    mockUseConfig.mockReturnValue({ data: MOCK_CONFIG })
    renderWithRoute()
    fireEvent.click(screen.getByRole('tab', { name: 'Raw JSON' }))
    expect(screen.getByText(/GET \/api\/v1\/observables\/:id/)).toBeTruthy()
    expect(screen.getByText(/"id"/)).toBeTruthy()
  })
})
