import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ObservableDetailPage from './ObservableDetailPage'

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockUseObservable = vi.fn()

vi.mock('@/hooks/useObservables', () => ({
  useObservable: (id: string | null) => mockUseObservable(id),
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

afterEach(cleanup)

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('ObservableDetailPage', () => {
  it('renders the observable value in mono text', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    renderWithRoute()
    expect(screen.getByText('5.188.206.18')).toBeTruthy()
  })

  it('renders the confidence band chip', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    renderWithRoute()
    // score 38 → Low band
    expect(screen.getByText('Low confidence')).toBeTruthy()
  })

  it('renders key-facts strip with source count and feeds reporting label', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    renderWithRoute()
    // source_count = 1
    expect(screen.getByText('1')).toBeTruthy()
    expect(screen.getByText('feeds reporting')).toBeTruthy()
  })

  it('Block button is disabled', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    renderWithRoute()
    const blockBtn = screen.getByRole('button', { name: /block/i })
    expect((blockBtn as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows a loading spinner while data is loading', () => {
    mockUseObservable.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderWithRoute()
    expect(screen.getByRole('status')).toBeTruthy() // LoadingSpinner aria-label="Loading"
    expect(screen.queryByText('5.188.206.18')).toBeNull()
  })

  it('renders the "Low band" label in key-facts confidence cell', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    renderWithRoute()
    expect(screen.getByText('Low band')).toBeTruthy()
  })

  it('passes the observable id from the route to useObservable', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    renderWithRoute('obs-abc-123')
    expect(mockUseObservable).toHaveBeenCalledWith('obs-abc-123')
  })
})
