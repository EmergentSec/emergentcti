import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { FeedCard } from './FeedCard'
import type { Feed } from '@/types/feed'
import { AxiosError, type AxiosResponse } from 'axios'

// ── Mock mutable refs so we can inspect calls ──────────────────────────────
const mockUpdateMutate = vi.fn()
const mockTriggerMutate = vi.fn()
const mockDeleteMutate = vi.fn()
const mockToast = vi.fn()

vi.mock('@/hooks/useFeeds', () => ({
  useUpdateFeed: () => ({ mutate: mockUpdateMutate, isPending: false }),
  useTriggerFeed: () => ({ mutate: mockTriggerMutate, isPending: false }),
  useDeleteFeed: () => ({ mutate: mockDeleteMutate, isPending: false }),
}))

const mockIsAdmin = { isAdmin: true }

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockIsAdmin,
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: mockToast }),
}))

vi.mock('./FeedRunHistory', () => ({
  FeedRunHistory: () => <div>run history</div>,
}))

// ── Fixture ─────────────────────────────────────────────────────────────────
const mockFeed: Feed = {
  id: '1',
  name: 'AbuseIPDB',
  description: 'Community-reported malicious IPs, confidence ≥ 90%.',
  feed_type: 'api',
  url: null,
  config: null,
  schedule_cron: '0 */6 * * *',
  enabled: true,
  is_preconfigured: true,
  has_auth: false,
  auth_supported: true,
  auth_needs_repair: false,
  default_confidence: 85,
  last_run_at: '2026-06-29T00:00:00Z',
  observable_count: 312480,
  latest_run: {
    id: 'run1',
    started_at: '2026-06-29T00:00:00Z',
    completed_at: '2026-06-29T00:05:00Z',
    status: 'failure',
    observables_ingested: 0,
    observables_new: 0,
    error_message: 'Connection timeout',
  },
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-06-29T00:00:00Z',
}

// ── Tests ───────────────────────────────────────────────────────────────────
describe('FeedCard', () => {
  afterEach(() => {
    cleanup()
    mockUpdateMutate.mockClear()
    mockTriggerMutate.mockClear()
    mockDeleteMutate.mockReset()
    mockToast.mockReset()
    vi.useRealTimers()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    mockIsAdmin.isAdmin = true
  })

  it('shows Auth needs repair badge when auth_needs_repair is true', () => {
    render(<FeedCard feed={{ ...mockFeed, auth_needs_repair: true }} />)
    expect(screen.getByText('Auth needs repair')).toBeTruthy()
  })

  it('does not show Auth needs repair badge when flag is false', () => {
    render(<FeedCard feed={mockFeed} />)
    expect(screen.queryByText('Auth needs repair')).toBeNull()
  })

  it('renders feed name and type chip', () => {
    render(<FeedCard feed={mockFeed} />)
    expect(screen.getByText('AbuseIPDB')).toBeTruthy()
    // Type chip label
    expect(screen.getByText('API')).toBeTruthy()
  })

  it('renders compact observable count in mono', () => {
    render(<FeedCard feed={mockFeed} />)
    // compactNumber(312480) → "312.5K"
    expect(screen.getByText('312.5K')).toBeTruthy()
  })

  it('renders failure status line', () => {
    render(<FeedCard feed={mockFeed} />)
    expect(screen.getByText('Error')).toBeTruthy()
  })

  it.each([
    { label: 'daily at 25h', schedule: '0 0 * * *', ageHours: 25, expected: 'OK' },
    { label: 'daily at 49h', schedule: '0 0 * * *', ageHours: 49, expected: 'Stale' },
    { label: 'every 2h at 5h', schedule: '0 */2 * * *', ageHours: 5, expected: 'Stale' },
    { label: 'no schedule at 25h', schedule: null, ageHours: 25, expected: 'Stale' },
  ])('derives staleness from the schedule: $label', ({ schedule, ageHours, expected }) => {
    const now = new Date('2026-06-30T12:00:00Z')
    vi.useFakeTimers()
    vi.setSystemTime(now)

    render(
      <FeedCard
        feed={{
          ...mockFeed,
          schedule_cron: schedule,
          last_run_at: new Date(now.getTime() - ageHours * 60 * 60 * 1000).toISOString(),
          latest_run: { ...mockFeed.latest_run!, status: 'success' },
        }}
      />,
    )

    expect(screen.getByText(expected)).toBeTruthy()
  })

  it('Run now button calls useTriggerFeed.mutate with feed id', () => {
    render(<FeedCard feed={mockFeed} />)
    const runBtn = screen.getByRole('button', { name: 'Run now' })
    fireEvent.click(runBtn)
    expect(mockTriggerMutate).toHaveBeenCalledWith('1', expect.anything())
  })

  it('Toggle calls useUpdateFeed.mutate with toggled enabled state', () => {
    render(<FeedCard feed={mockFeed} />)
    // feed.enabled = true; clicking toggle should request enabled: false
    const toggle = screen.getByRole('switch')
    fireEvent.click(toggle)
    expect(mockUpdateMutate).toHaveBeenCalledWith(
      { id: '1', data: { enabled: false } },
      expect.anything(),
    )
  })

  it('explains why a feed referenced by an export profile cannot be deleted', () => {
    const detail = 'Feed is referenced by export profiles. Update or delete them first.'
    const error = new AxiosError('Request failed with status code 409')
    error.response = { status: 409, data: { detail } } as AxiosResponse
    mockDeleteMutate.mockImplementation((_id, callbacks) => callbacks.onError(error))
    render(<FeedCard feed={{ ...mockFeed, is_preconfigured: false }} />)
    fireEvent.click(screen.getByRole('button', { name: 'Feed options' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(mockDeleteMutate).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Delete feed' }))
    expect(mockDeleteMutate).toHaveBeenCalledWith('1', expect.anything())
    expect(mockToast).toHaveBeenCalledWith(detail, 'error')
  })

  it('disables Run now and Toggle for non-admin users', () => {
    mockIsAdmin.isAdmin = false
    render(<FeedCard feed={mockFeed} />)
    const runBtn = screen.getByRole('button', { name: 'Run now' })
    expect(runBtn.hasAttribute('disabled')).toBe(true)
    const toggle = screen.getByRole('switch')
    expect(toggle.hasAttribute('disabled')).toBe(true)
  })

  it('admin: opening the ⋮ menu shows Edit', () => {
    render(<FeedCard feed={mockFeed} />)
    fireEvent.click(screen.getByRole('button', { name: 'Feed options' }))
    expect(screen.getByRole('button', { name: 'Edit' })).toBeTruthy()
  })

  it('admin: clicking Edit calls onEdit with the feed', () => {
    const onEdit = vi.fn()
    render(<FeedCard feed={mockFeed} onEdit={onEdit} />)
    fireEvent.click(screen.getByRole('button', { name: 'Feed options' }))
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(onEdit).toHaveBeenCalledWith(mockFeed)
  })

  it('non-admin: Edit is not rendered in the ⋮ menu', () => {
    mockIsAdmin.isAdmin = false
    render(<FeedCard feed={mockFeed} />)
    fireEvent.click(screen.getByRole('button', { name: 'Feed options' }))
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull()
  })

  it('admin: Edit is shown for a preconfigured feed', () => {
    const preconfigFeed = { ...mockFeed, is_preconfigured: true }
    render(<FeedCard feed={preconfigFeed} />)
    fireEvent.click(screen.getByRole('button', { name: 'Feed options' }))
    expect(screen.getByRole('button', { name: 'Edit' })).toBeTruthy()
  })
})
