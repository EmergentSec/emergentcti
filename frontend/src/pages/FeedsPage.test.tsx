import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import FeedsPage from './FeedsPage'
import type { Feed } from '@/types/feed'
import { FEED_TLP_FIELD } from '@/test/fixtures/feed'

// ── Stub heavy sub-components ────────────────────────────────────────────────

vi.mock('@/components/feeds/FeedCard', () => ({
  FeedCard: ({
    feed,
    onEdit,
    highlighted,
  }: {
    feed: Feed
    onEdit?: (feed: Feed) => void
    highlighted?: boolean
  }) => (
    <div
      data-testid="feed-card"
      id={`feed-${feed.id}`}
      data-feed-id={feed.id}
      data-highlighted={highlighted ? 'true' : 'false'}
      data-feed-type={feed.feed_type}
    >
      {feed.name}
      {onEdit && (
        <button onClick={() => onEdit(feed)}>trigger-edit-{feed.id}</button>
      )}
    </div>
  ),
}))

vi.mock('@/components/feeds/FeedForm', () => ({
  FeedForm: ({
    onSubmit,
    initialValues,
  }: {
    onSubmit: (data: Record<string, unknown>) => void
    initialValues?: Feed
  }) => (
    <div data-testid="feed-form">
      {initialValues && (
        <button
          data-testid="feed-form-submit"
          onClick={() => onSubmit({ name: initialValues.name })}
        >
          Save
        </button>
      )}
    </div>
  ),
}))

vi.mock('@/components/ui/Dialog', () => ({
  Dialog: ({
    open,
    children,
    title,
  }: {
    open: boolean
    children: React.ReactNode
    title: string
  }) =>
    open ? (
      <div data-testid="dialog" aria-label={title}>
        {children}
      </div>
    ) : null,
}))

// ── Hook mocks ───────────────────────────────────────────────────────────────

const mockFeeds: Feed[] = [
  {
    id: 'f1',
    name: 'AbuseIPDB',
    description: null,
    feed_type: 'api',
    url: null,
    config: null,
    schedule_cron: null,
    enabled: true,
    is_preconfigured: true,
    has_auth: false,
    auth_supported: true,
    auth_needs_repair: false,
    default_confidence: 80,
    ...FEED_TLP_FIELD,
    last_run_at: null,
    observable_count: 1000,
    latest_run: null,
    created_at: '',
    updated_at: '',
  },
  {
    id: 'f2',
    name: 'MalwareBazaar',
    description: null,
    feed_type: 'api',
    url: null,
    config: null,
    schedule_cron: null,
    enabled: true,
    is_preconfigured: true,
    has_auth: false,
    auth_supported: false,
    auth_needs_repair: false,
    default_confidence: 90,
    ...FEED_TLP_FIELD,
    last_run_at: null,
    observable_count: 500,
    latest_run: null,
    created_at: '',
    updated_at: '',
  },
  {
    id: 'f3',
    name: 'Local File',
    description: null,
    feed_type: 'file',
    url: null,
    config: null,
    schedule_cron: null,
    enabled: false,
    is_preconfigured: false,
    has_auth: false,
    auth_supported: false,
    auth_needs_repair: false,
    default_confidence: 70,
    ...FEED_TLP_FIELD,
    last_run_at: null,
    observable_count: 200,
    latest_run: null,
    created_at: '',
    updated_at: '',
  },
]

const mockDashboard = {
  total_observables: 1750,
  total_feeds: 3,
  feeds_enabled: 2,
  last_24h_ingested: 150,
  feed_errors_24h: 5,
  by_type: {},
  feeds_health: [],
  confidence_distribution: { critical: 0, high: 0, medium: 0, low: 0 },
  daily_ingest_14d: [],
}

const mockUpdateMutate = vi.fn()

vi.mock('@/hooks/useFeeds', () => ({
  // A fresh array per render, like a react-query refetch after a mutation.
  useFeeds: () => ({ data: [...mockFeeds], isLoading: false, error: null }),
  useCreateFeed: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateFeed: () => ({ mutate: mockUpdateMutate, isPending: false }),
}))

vi.mock('@/hooks/useDashboard', () => ({
  useDashboard: () => ({ data: mockDashboard }),
}))

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ isAdmin: true }),
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

// ── Helpers ──────────────────────────────────────────────────────────────────

function renderPage() {
  return render(
    <MemoryRouter>
      <FeedsPage />
    </MemoryRouter>,
  )
}

// ── Tests ────────────────────────────────────────────────────────────────────

afterEach(cleanup)

describe('FeedsPage — summary cards', () => {
  it('shows Configured feeds count', () => {
    renderPage()
    expect(screen.getByText('Configured feeds')).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy() // feeds.length
  })

  it('shows Enabled count', () => {
    renderPage()
    expect(screen.getByText('Enabled')).toBeTruthy()
    expect(screen.getByText('2')).toBeTruthy() // 2 of 3 enabled
  })

  it('shows Errors (24h) from useDashboard', () => {
    renderPage()
    expect(screen.getByText('Errors (24h)')).toBeTruthy()
    expect(screen.getByText('5')).toBeTruthy() // feed_errors_24h
  })

  it('shows Observables count from useDashboard', () => {
    renderPage()
    expect(screen.getByText('Observables')).toBeTruthy()
    // compactNumber(1750) → '1.8K'
    expect(screen.getByText('1.8K')).toBeTruthy()
  })
})

describe('FeedsPage — segmented filter', () => {
  it('renders all 4 filter segments', () => {
    renderPage()
    expect(screen.getByRole('tab', { name: 'All' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'API' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'File' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Scraper' })).toBeTruthy()
  })

  it('shows all feeds by default', () => {
    renderPage()
    expect(screen.getAllByTestId('feed-card')).toHaveLength(3)
  })

  it('selecting "API" filters to only api feeds', () => {
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'API' }))
    const cards = screen.getAllByTestId('feed-card')
    expect(cards).toHaveLength(2)
    cards.forEach((card) =>
      expect(card.getAttribute('data-feed-type')).toBe('api'),
    )
  })

  it('selecting "File" filters to file feeds only', () => {
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'File' }))
    const cards = screen.getAllByTestId('feed-card')
    expect(cards).toHaveLength(1)
    expect(cards[0].getAttribute('data-feed-type')).toBe('file')
  })

  it('selecting "Scraper" shows empty state when no scraper feeds', () => {
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Scraper' }))
    expect(screen.queryAllByTestId('feed-card')).toHaveLength(0)
    expect(screen.getByText(/no scraper feeds/i)).toBeTruthy()
  })

  it('switching back to "All" restores full list', () => {
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'API' }))
    fireEvent.click(screen.getByRole('tab', { name: 'All' }))
    expect(screen.getAllByTestId('feed-card')).toHaveLength(3)
  })
})

describe('FeedsPage — Add Feed', () => {
  it('renders the Add Feed button for admins', () => {
    renderPage()
    expect(screen.getByRole('button', { name: /add feed/i })).toBeTruthy()
  })

  it('opens the create dialog when Add Feed is clicked', () => {
    renderPage()
    expect(screen.queryByTestId('dialog')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /add feed/i }))
    expect(screen.getByTestId('dialog')).toBeTruthy()
    expect(screen.getByTestId('feed-form')).toBeTruthy()
  })

  it('opens the create dialog from the ?create=1 deep link', () => {
    render(
      <MemoryRouter initialEntries={['/feeds?create=1']}>
        <FeedsPage />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('dialog')).toBeTruthy()
    expect(screen.getByTestId('feed-form')).toBeTruthy()
  })
})

describe('FeedsPage — Edit Feed', () => {
  afterEach(() => {
    mockUpdateMutate.mockClear()
  })

  it('opens the Edit Feed dialog when a FeedCard triggers onEdit', () => {
    renderPage()
    expect(screen.queryByTestId('dialog')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'trigger-edit-f1' }))
    const dialog = screen.getByTestId('dialog')
    expect(dialog).toBeTruthy()
    expect(dialog.getAttribute('aria-label')).toBe('Edit Feed')
    expect(screen.getByTestId('feed-form')).toBeTruthy()
  })

  it('submitting the edit form calls useUpdateFeed mutate with { id, data }', () => {
    renderPage()
    // Open the edit dialog for feed f1 (AbuseIPDB)
    fireEvent.click(screen.getByRole('button', { name: 'trigger-edit-f1' }))
    // Submit via the Save button rendered by the FeedForm stub when initialValues is set
    fireEvent.click(screen.getByTestId('feed-form-submit'))
    expect(mockUpdateMutate).toHaveBeenCalledWith(
      { id: 'f1', data: { name: 'AbuseIPDB' } },
      expect.anything(),
    )
  })

  it('highlights the feed named in ?feed= and scrolls it into view', () => {
    const scrollIntoView = vi.spyOn(Element.prototype, 'scrollIntoView').mockImplementation(() => {})
    try {
      render(
        <MemoryRouter initialEntries={['/feeds?feed=f2']}>
          <FeedsPage />
        </MemoryRouter>,
      )

      expect(document.getElementById('feed-f2')?.getAttribute('data-highlighted')).toBe('true')
      expect(document.getElementById('feed-f1')?.getAttribute('data-highlighted')).toBe('false')
      expect(scrollIntoView).toHaveBeenCalledTimes(1)
      expect(screen.queryByText(/linked feed was not found/i)).toBeNull()

      // A rerender with refetched feeds (new array) must not scroll again.
      fireEvent.click(screen.getByRole('button', { name: 'trigger-edit-f1' }))
      expect(scrollIntoView).toHaveBeenCalledTimes(1)
    } finally {
      scrollIntoView.mockRestore()
    }
  })

  it('shows a dismissible notice when ?feed= names an unknown or deleted feed', () => {
    const scrollIntoView = vi.spyOn(Element.prototype, 'scrollIntoView').mockImplementation(() => {})
    try {
      render(
        <MemoryRouter initialEntries={['/feeds?feed=deleted-feed']}>
          <FeedsPage />
        </MemoryRouter>,
      )

      expect(screen.getByRole('status').textContent).toMatch(/linked feed was not found/i)
      expect(scrollIntoView).not.toHaveBeenCalled()
      // Existing feeds still render, none highlighted.
      expect(screen.getAllByTestId('feed-card')).toHaveLength(mockFeeds.length)
      expect(
        screen.getAllByTestId('feed-card').every((el) => el.getAttribute('data-highlighted') === 'false'),
      ).toBe(true)

      fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
      expect(screen.queryByText(/linked feed was not found/i)).toBeNull()
    } finally {
      scrollIntoView.mockRestore()
    }
  })
})
