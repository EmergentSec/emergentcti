import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ReportDetailPage from './ReportDetailPage'

const mockUseReport = vi.fn()
const mockUpdate = vi.fn()
const mockDelete = vi.fn()
const mockUploadAttachment = vi.fn()
const mockRemoveAttachment = vi.fn()
const mockExtract = vi.fn()
const mockToast = vi.fn()

vi.mock('@/hooks/useReports', () => ({
  useReport: (id: string | null) => mockUseReport(id),
  useUpdateReport: () => ({ mutate: mockUpdate, isPending: false }),
  useDeleteReport: () => ({ mutate: mockDelete, isPending: false }),
  useUploadReportAttachment: () => ({ mutate: mockUploadAttachment, isPending: false }),
  useRemoveReportAttachment: () => ({ mutate: mockRemoveAttachment, isPending: false }),
  useLinkReportObservable: () => ({ mutate: vi.fn(), isPending: false }),
  useUnlinkReportObservable: () => ({ mutate: vi.fn(), isPending: false }),
  useExtractReportIndicators: () => ({ mutate: mockExtract, isPending: false }),
  useImportReportIndicators: () => ({ mutate: vi.fn(), isPending: false }),
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
  useToast: () => ({ toast: mockToast }),
}))

vi.mock('@/components/reports/ReportForm', () => ({
  ReportForm: () => <div data-testid="report-form" />,
}))

import { AxiosError } from 'axios'

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

const REPORT_WITH_ATTACHMENT = {
  ...AI_REPORT,
  has_attachment: true,
  attachment: {
    original_filename: 'brief.pdf',
    size_bytes: 1024,
    content_type: 'application/pdf',
  },
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
  mockUploadAttachment.mockReset()
  mockRemoveAttachment.mockReset()
  mockExtract.mockReset()
  mockToast.mockReset()
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
    expect(screen.queryByRole('button', { name: 'Extract indicators' })).toBeNull()
  })

  it('shows extract button for admins and opens import review on success', () => {
    mockUseReport.mockReturnValue({ data: AI_REPORT, isLoading: false, error: null })
    mockExtract.mockImplementation((_id, options) => {
      options?.onSuccess?.({
        report_id: 'rep-1',
        sources: [],
        candidates: [],
        truncated: false,
        counts: { total: 0, new: 0, existing: 0, invalid: 0 },
      })
    })

    renderPage()

    const extractBtn = screen.getByRole('button', { name: 'Extract indicators' })
    fireEvent.click(extractBtn)

    expect(mockExtract).toHaveBeenCalledWith('rep-1', expect.any(Object))
    expect(screen.getByRole('dialog', { name: 'Import indicators from report' })).toBeTruthy()
  })

  it('toasts on extract failure', () => {
    mockUseReport.mockReturnValue({ data: AI_REPORT, isLoading: false, error: null })
    mockExtract.mockImplementation((_id, options) => {
      const err = new AxiosError('Request failed')
      err.response = {
        status: 500,
        data: { detail: 'Extract failed' },
        statusText: 'Error',
        headers: {},
        config: {} as never,
      }
      options?.onError?.(err)
    })

    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Extract indicators' }))

    expect(mockToast).toHaveBeenCalledWith('Extract failed', 'error')
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

  it('requires confirmation before removing attachment', () => {
    mockUseReport.mockReturnValue({
      data: REPORT_WITH_ATTACHMENT,
      isLoading: false,
      error: null,
    })
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }))
    expect(screen.getByRole('dialog', { name: 'Remove attachment' })).toBeTruthy()
    expect(mockRemoveAttachment).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Remove attachment' }))
    expect(mockRemoveAttachment).toHaveBeenCalledWith('rep-1', expect.any(Object))
  })

  it('surfaces API detail text on upload failure', () => {
    mockUseReport.mockReturnValue({
      data: REPORT_WITH_ATTACHMENT,
      isLoading: false,
      error: null,
    })
    mockUploadAttachment.mockImplementation((_args, options) => {
      const err = new AxiosError('Request failed')
      err.response = {
        status: 415,
        data: { detail: 'Unsupported media type' },
        statusText: 'Unsupported Media Type',
        headers: {},
        config: {} as never,
      }
      options?.onError?.(err)
    })

    renderPage()

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['x'], 'bad.exe', { type: 'application/octet-stream' })
    fireEvent.change(input, { target: { files: [file] } })

    expect(mockToast).toHaveBeenCalledWith('Unsupported media type', 'error')
  })
})
