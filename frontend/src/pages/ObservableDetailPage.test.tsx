import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
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

  it('Block button is disabled', () => {
    mockUseObservable.mockReturnValue({ data: MOCK_OBS, isLoading: false, error: null })
    mockUseConfig.mockReturnValue({ data: MOCK_CONFIG })
    renderWithRoute()
    const blockBtn = screen.getByRole('button', { name: /block/i })
    expect((blockBtn as HTMLButtonElement).disabled).toBe(true)
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
