import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ObservablesPage from './ObservablesPage'
import type { ObservableFilters as Filters } from '@/types/observable'

// Stub heavy sub-components to isolate the page shell
vi.mock('@/components/observables/ObservableFilters', () => ({
  ObservableFilters: () => <div data-testid="observable-filters" />,
}))

vi.mock('@/components/observables/ObservableTable', () => ({
  ObservableTable: () => <div data-testid="observable-table" />,
}))

// Stub the create form so we can detect whether the dialog is open
vi.mock('@/components/observables/ObservableForm', () => ({
  ObservableForm: () => <div data-testid="observable-form" />,
}))

const mockUseObservables = vi.fn()

vi.mock('@/hooks/useObservables', () => ({
  useObservables: (params: Filters) => mockUseObservables(params),
  useCreateObservable: () => ({ mutate: vi.fn(), isPending: false }),
}))

const { mockAuth } = vi.hoisted(() => ({ mockAuth: { isAdmin: false } }))
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

afterEach(() => {
  cleanup()
  mockAuth.isAdmin = false
})

const ITEMS = [
  {
    id: 'obs-1',
    type: 'ip-addr' as const,
    value: '1.2.3.4',
    confidence_score: 80,
    first_seen: null,
    last_seen: null,
    source_count: 0,
    sources: [],
    created_at: '',
    updated_at: '',
  },
]

const DEFAULT_DATA = {
  items: ITEMS,
  total: 16,
  page: 1,
  pages: 2,
}

describe('ObservablesPage', () => {
  it('renders the filter toolbar stub', () => {
    mockUseObservables.mockReturnValue({ data: DEFAULT_DATA, isLoading: false, error: null })
    render(
      <MemoryRouter>
        <ObservablesPage />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('observable-filters')).toBeTruthy()
  })

  it('renders count header with total observables', () => {
    mockUseObservables.mockReturnValue({ data: DEFAULT_DATA, isLoading: false, error: null })
    render(
      <MemoryRouter>
        <ObservablesPage />
      </MemoryRouter>,
    )
    expect(screen.getByText('16 observables')).toBeTruthy()
  })

  it('renders Sort select with Last seen as default option', () => {
    mockUseObservables.mockReturnValue({ data: DEFAULT_DATA, isLoading: false, error: null })
    render(
      <MemoryRouter>
        <ObservablesPage />
      </MemoryRouter>,
    )
    expect(screen.getByDisplayValue('Last seen')).toBeTruthy()
    // All four sort options should be present
    expect(screen.getByText('Last seen')).toBeTruthy()
    expect(screen.getByText('Confidence')).toBeTruthy()
    expect(screen.getByText('First seen')).toBeTruthy()
    expect(screen.getByText('Value')).toBeTruthy()
  })

  it('changing sort select updates useObservables params with new sort and resets page to 1', () => {
    mockUseObservables.mockReturnValue({ data: DEFAULT_DATA, isLoading: false, error: null })
    render(
      <MemoryRouter>
        <ObservablesPage />
      </MemoryRouter>,
    )

    const sortSelect = screen.getByDisplayValue('Last seen')
    fireEvent.change(sortSelect, { target: { value: 'confidence_score' } })

    // After the change, useObservables must have been called with updated sort + page reset
    expect(mockUseObservables).toHaveBeenCalledWith(
      expect.objectContaining({ sort: 'confidence_score', page: 1 }),
    )
  })

  it('renders the observable table stub when items exist', () => {
    mockUseObservables.mockReturnValue({ data: DEFAULT_DATA, isLoading: false, error: null })
    render(
      <MemoryRouter>
        <ObservablesPage />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('observable-table')).toBeTruthy()
  })

  it('renders Pagination when data is present', () => {
    mockUseObservables.mockReturnValue({ data: DEFAULT_DATA, isLoading: false, error: null })
    render(
      <MemoryRouter>
        <ObservablesPage />
      </MemoryRouter>,
    )
    // Pagination renders "Page X of Y (Z total)" text
    expect(screen.getByText('Page 1 of 2 (16 total)')).toBeTruthy()
  })

  it('shows loading spinner while data loads', () => {
    mockUseObservables.mockReturnValue({ data: undefined, isLoading: true, error: null })
    render(
      <MemoryRouter>
        <ObservablesPage />
      </MemoryRouter>,
    )
    // No table or count while loading
    expect(screen.queryByText(/observables/)).toBeNull()
    expect(screen.queryByTestId('observable-table')).toBeNull()
  })

  it('opens the create dialog when routed with ?create=1 as admin (topbar Add Observable)', () => {
    mockAuth.isAdmin = true
    mockUseObservables.mockReturnValue({ data: DEFAULT_DATA, isLoading: false, error: null })
    render(
      <MemoryRouter initialEntries={['/observables?create=1']}>
        <ObservablesPage />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('observable-form')).toBeTruthy()
  })

  it('does not open the create dialog from ?create=1 for non-admins', () => {
    mockAuth.isAdmin = false
    mockUseObservables.mockReturnValue({ data: DEFAULT_DATA, isLoading: false, error: null })
    render(
      <MemoryRouter initialEntries={['/observables?create=1']}>
        <ObservablesPage />
      </MemoryRouter>,
    )
    expect(screen.queryByTestId('observable-form')).toBeNull()
  })
})
