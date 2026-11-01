import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ReportDetailPage from './ReportDetailPage'

const mockUseReport = vi.fn()
const mockUpdate = vi.fn()
const mockDelete = vi.fn()

vi.mock('@/hooks/useReports', () => ({
  useReport: (id: string | null) => mockUseReport(id),
  useUpdateReport: () => ({ mutate: mockUpdate, isPending: false }),
  useDeleteReport: () => ({ mutate: mockDelete, isPending: false }),
  useUploadReportAttachment: () => ({ mutate: vi.fn(), isPending: false }),
  useRemoveReportAttachment: () => ({ mutate: vi.fn(), isPending: false }),
  useLinkReportObservable: () => ({ mutate: vi.fn(), isPending: false }),
  useUnlinkReportObservable: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/hooks/useObservables', () => ({
  useObservables: () => ({ data: { items: [] } }),
}))

vi.mock('@/api/reports', () => ({
  downloadReportAttachment: vi.fn(),
}))

const { mockAuth } = vi.hoisted(() => ({ mockAuth: { isAdmin: true } }))
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}))
vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

vi.mock('@/components/reports/ReportForm', () => ({
  ReportForm: () => <div data-testid="report-form" />,
}))

const AI_REPORT = {
  id: 'rep-1',
  title: 'AI summary',
  origin: 'internal' as const,
  source_name: 'Team',
  published_at: null,
  summary: null,
  is_ai_generated: true,
  ai_provider: null,
  ai_model: null,
  has_attachment: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  source_url: null,
  content: 'Body',
  content_format: 'markdown' as const,
  ai_generated_at: null,
  created_by: 'admin',
  attachment: null,
  observables: [],
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/reports/rep-1']}>
      <Routes>
        <Route path="/reports/:id" element={<ReportDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  mockAuth.isAdmin = true
  mockDelete.mockReset()
})

describe('ReportDetailPage', () => {
  it('shows AI badge and Unknown provenance fields', () => {
    mockUseReport.mockReturnValue({ data: AI_REPORT, isLoading: false, error: null })
    renderPage()

    expect(screen.getByText('AI-generated')).toBeTruthy()
    expect(screen.getAllByText('Unknown').length).toBeGreaterThanOrEqual(2)
  })

  it('hides admin controls for analysts', () => {
    mockAuth.isAdmin = false
    mockUseReport.mockReturnValue({ data: AI_REPORT, isLoading: false, error: null })
    renderPage()

    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Link observable' })).toBeNull()
  })

  it('requires confirmation before delete', () => {
    mockUseReport.mockReturnValue({ data: AI_REPORT, isLoading: false, error: null })
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(screen.getByRole('dialog', { name: 'Delete report' })).toBeTruthy()
    expect(mockDelete).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Delete report' }))
    expect(mockDelete).toHaveBeenCalledWith('rep-1', expect.any(Object))
  })
})
