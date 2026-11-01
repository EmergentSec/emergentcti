import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ReportsPage from './ReportsPage'
import { ReportTagsSaveError } from '@/api/reports'
import type { ReportFilters } from '@/types/report'
import { EMPTY_TLP_REPORT_FIELDS } from '@/test/fixtures/tlp'

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
const { mockToast } = vi.hoisted(() => ({ mockToast: vi.fn() }))
vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: mockToast }),
}))

vi.mock('@/hooks/useTags', () => ({
  useTags: () => ({ data: [] }),
}))

vi.mock('@/components/reports/ReportForm', () => ({
  ReportForm: ({ onSubmit }: { onSubmit: (payload: unknown) => void }) => (
    <div data-testid="report-form">
      <button onClick={() => onSubmit({ title: 'New', origin: 'internal', tags: ['missing'] })}>
        submit-report
      </button>
    </div>
  ),
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
    ...EMPTY_TLP_REPORT_FIELDS,
    created_at: '',
    updated_at: '',
  },
]

const LIST = { items: ITEMS, total: 30, page: 1, size: 25, pages: 2 }

afterEach(() => {
  cleanup()
  mockAuth.isAdmin = false
  mockUseReports.mockReset()
  mockCreateReport.mockReset()
  mockToast.mockReset()
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

  it('ignores ?create=1 and hides create controls for analysts', () => {
    mockUseReportSources.mockReturnValue({ data: [] })
    mockUseReports.mockReturnValue({
      data: { items: [], total: 0, page: 1, size: 25, pages: 0 },
      isLoading: false,
      error: null,
    })

    render(
      <MemoryRouter initialEntries={['/reports?create=1']}>
        <ReportsPage />
      </MemoryRouter>,
    )

    expect(screen.queryByRole('button', { name: 'New report' })).toBeNull()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('opens the create dialog for admins via ?create=1 (masthead button target)', () => {
    mockAuth.isAdmin = true
    mockUseReportSources.mockReturnValue({ data: [] })
    mockUseReports.mockReturnValue({ data: LIST, isLoading: false, error: null })

    render(
      <MemoryRouter initialEntries={['/reports?create=1']}>
        <ReportsPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  it('offers New report in the empty state for admins', () => {
    mockAuth.isAdmin = true
    mockUseReportSources.mockReturnValue({ data: [] })
    mockUseReports.mockReturnValue({
      data: { items: [], total: 0, page: 1, size: 25, pages: 0 },
      isLoading: false,
      error: null,
    })

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: 'New report' })).toBeTruthy()
  })

  it('opens the created report when tags fail to save, without leaving a retry path', () => {
    mockAuth.isAdmin = true
    mockUseReportSources.mockReturnValue({ data: [] })
    mockUseReports.mockReturnValue({ data: LIST, isLoading: false, error: null })
    mockCreateReport.mockImplementation((_payload, opts: { onError: (err: unknown) => void }) => {
      opts.onError(
        new ReportTagsSaveError({ ...ITEMS[0], id: 'r9' } as never, {
          isAxiosError: true,
          response: { data: { detail: 'Tag not found: missing' } },
        }),
      )
    })

    render(
      <MemoryRouter initialEntries={['/reports?create=1']}>
        <Routes>
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:id" element={<p>report detail page</p>} />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'submit-report' }))

    expect(mockCreateReport).toHaveBeenCalledTimes(1)
    expect(screen.getByText('report detail page')).toBeTruthy()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(mockToast).toHaveBeenCalledWith(
      expect.stringMatching(/Report created, but tags couldn't be saved: Tag not found: missing/),
      'error',
    )
  })
})
