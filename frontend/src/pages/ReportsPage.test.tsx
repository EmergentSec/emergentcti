import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ReportsPage from './ReportsPage'
import type { ReportFilters } from '@/types/report'

const mockUseReports = vi.fn()
const mockUseReportSources = vi.fn()
const mockCreateReport = vi.fn()

vi.mock('@/hooks/useReports', () => ({
  useReports: (filters: ReportFilters) => mockUseReports(filters),
  useReportSources: () => mockUseReportSources(),
  useCreateReport: () => ({ mutate: mockCreateReport, isPending: false }),
}))

const { mockAuth } = vi.hoisted(() => ({ mockAuth: { isAdmin: false } }))
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}))
vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

vi.mock('@/components/reports/ReportForm', () => ({
  ReportForm: () => <div data-testid="report-form" />,
}))

const ITEMS = [
  {
    id: 'r1',
    title: 'APT Report',
    origin: 'provider' as const,
    source_name: 'Mandiant',
    published_at: '2026-01-01T00:00:00Z',
    summary: 'Summary text',
    is_ai_generated: false,
    ai_provider: null,
    ai_model: null,
    has_attachment: true,
    created_at: '',
    updated_at: '',
  },
]

const LIST = { items: ITEMS, total: 30, page: 1, size: 25, pages: 2 }

afterEach(() => {
  cleanup()
  mockAuth.isAdmin = false
  mockUseReports.mockReset()
})

describe('ReportsPage', () => {
  it('renders search and passes filters to the hook', () => {
    mockUseReportSources.mockReturnValue({ data: ['Mandiant'] })
    mockUseReports.mockReturnValue({ data: LIST, isLoading: false, error: null })

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText('Search reports by title or summary'), {
      target: { value: 'APT' },
    })

    expect(mockUseReports).toHaveBeenCalledWith(expect.objectContaining({ q: 'APT', page: 1 }))
    expect(screen.getByText('30 reports')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'APT Report' })).toBeTruthy()
  })

  it('filters by origin and paginates', () => {
    mockUseReportSources.mockReturnValue({ data: [] })
    mockUseReports.mockReturnValue({ data: LIST, isLoading: false, error: null })

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText('Filter by origin'), { target: { value: 'internal' } })
    expect(mockUseReports).toHaveBeenCalledWith(
      expect.objectContaining({ origin: 'internal', page: 1 }),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(mockUseReports).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))
  })

  it('hides New report for analysts', () => {
    mockUseReportSources.mockReturnValue({ data: [] })
    mockUseReports.mockReturnValue({ data: LIST, isLoading: false, error: null })

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    )

    expect(screen.queryByRole('button', { name: 'New report' })).toBeNull()
  })

  it('shows New report for admins', () => {
    mockAuth.isAdmin = true
    mockUseReportSources.mockReturnValue({ data: [] })
    mockUseReports.mockReturnValue({ data: LIST, isLoading: false, error: null })

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: 'New report' })).toBeTruthy()
  })
})
