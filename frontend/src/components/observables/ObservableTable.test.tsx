import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ObservableTable } from './ObservableTable'
import type { Observable } from '@/types/observable'

// Spy on navigate — must be set before vi.mock runs
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('@/hooks/useObservables', () => ({
  useDeleteObservable: () => ({ mutate: vi.fn(), isPending: false }),
}))

const mockUseAuth = vi.fn(() => ({ isAdmin: true }) as ReturnType<typeof import('@/contexts/AuthContext').useAuth>)

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}))

const OBSERVABLES: Observable[] = [
  {
    id: 'obs-1',
    type: 'ip-addr',
    value: '5.188.206.18',
    confidence_score: 38,
    first_seen: '2026-06-27T00:00:00Z',
    last_seen: '2026-06-28T00:00:00Z',
    source_count: 1,
    sources: [
      {
        feed_id: 'f1',
        feed_name: 'Blocklist.de',
        source_confidence: 38,
        native_confidence: 38,
        first_seen_by_feed: '2026-06-27T00:00:00Z',
        last_seen_by_feed: '2026-06-28T00:00:00Z',
      },
    ],
    created_at: '2026-06-27T00:00:00Z',
    updated_at: '2026-06-28T00:00:00Z',
  },
  {
    id: 'obs-2',
    type: 'url',
    value: 'http://194.5.250.100/payload',
    confidence_score: 78,
    first_seen: '2026-06-29T00:00:00Z',
    last_seen: '2026-06-29T20:00:00Z',
    source_count: 3,
    sources: [
      {
        feed_id: 'f2',
        feed_name: 'URLhaus',
        source_confidence: 78,
        native_confidence: 78,
        first_seen_by_feed: '2026-06-29T00:00:00Z',
        last_seen_by_feed: '2026-06-29T20:00:00Z',
      },
      {
        feed_id: 'f3',
        feed_name: 'Feodo Tracker',
        source_confidence: 75,
        native_confidence: 75,
        first_seen_by_feed: '2026-06-29T00:00:00Z',
        last_seen_by_feed: '2026-06-29T20:00:00Z',
      },
      {
        feed_id: 'f4',
        feed_name: 'ThreatFox',
        source_confidence: 80,
        native_confidence: 80,
        first_seen_by_feed: '2026-06-29T00:00:00Z',
        last_seen_by_feed: '2026-06-29T20:00:00Z',
      },
    ],
    created_at: '2026-06-29T00:00:00Z',
    updated_at: '2026-06-29T20:00:00Z',
  },
]

afterEach(cleanup)

beforeEach(() => {
  mockNavigate.mockClear()
})

describe('ObservableTable', () => {
  it('renders the type label for each observable', () => {
    render(
      <MemoryRouter>
        <ObservableTable observables={OBSERVABLES} />
      </MemoryRouter>,
    )
    expect(screen.getByText('IP Address')).toBeTruthy()
    expect(screen.getByText('URL')).toBeTruthy()
  })

  it('renders observable values', () => {
    render(
      <MemoryRouter>
        <ObservableTable observables={OBSERVABLES} />
      </MemoryRouter>,
    )
    expect(screen.getByText('5.188.206.18')).toBeTruthy()
    expect(screen.getByText('http://194.5.250.100/payload')).toBeTruthy()
  })

  it('renders confidence band labels (Low for 38, High for 78)', () => {
    render(
      <MemoryRouter>
        <ObservableTable observables={OBSERVABLES} />
      </MemoryRouter>,
    )
    // obs-1: score 38 → Low
    expect(screen.getByText('Low')).toBeTruthy()
    // obs-2: score 78 → High
    expect(screen.getByText('High')).toBeTruthy()
  })

  it('navigates to /observables/:id when a row is clicked', () => {
    const { container } = render(
      <MemoryRouter>
        <ObservableTable observables={OBSERVABLES} />
      </MemoryRouter>,
    )

    const rows = container.querySelectorAll('tr[role="button"]')
    expect(rows.length).toBe(2)

    fireEvent.click(rows[0])
    expect(mockNavigate).toHaveBeenCalledWith('/observables/obs-1')

    fireEvent.click(rows[1])
    expect(mockNavigate).toHaveBeenCalledWith('/observables/obs-2')
  })

  it('shows source feed chips (first 2 + overflow +N)', () => {
    render(
      <MemoryRouter>
        <ObservableTable observables={OBSERVABLES} />
      </MemoryRouter>,
    )
    // obs-1: 1 source
    expect(screen.getByText('Blocklist.de')).toBeTruthy()
    // obs-2: 3 sources → 2 shown + +1 overflow
    expect(screen.getByText('URLhaus')).toBeTruthy()
    expect(screen.getByText('Feodo Tracker')).toBeTruthy()
    expect(screen.getByText('+1')).toBeTruthy()
  })

  it('shows Manual chip when sources is empty', () => {
    const noSource: Observable[] = [
      { ...OBSERVABLES[0], id: 'obs-manual', sources: [], source_count: 0 },
    ]
    render(
      <MemoryRouter>
        <ObservableTable observables={noSource} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Manual')).toBeTruthy()
  })

  it('does not navigate when the Delete button is clicked', () => {
    // Delete button should stopPropagation — row click must not fire
    window.confirm = vi.fn(() => false) // cancel the confirm dialog
    render(
      <MemoryRouter>
        <ObservableTable observables={OBSERVABLES} />
      </MemoryRouter>,
    )
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    fireEvent.click(deleteButtons[0])
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('hides the delete button for non-admin users', () => {
    mockUseAuth.mockReturnValueOnce({ isAdmin: false } as ReturnType<typeof import('@/contexts/AuthContext').useAuth>)
    render(
      <MemoryRouter>
        <ObservableTable observables={OBSERVABLES} />
      </MemoryRouter>,
    )
    expect(screen.queryAllByRole('button', { name: /delete/i })).toHaveLength(0)
  })
})
