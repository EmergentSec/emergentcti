import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosError, type AxiosResponse } from 'axios'
import { IndicatorImportReview } from './IndicatorImportReview'
import type { ExtractionPreview } from '@/types/reportIocExtraction'
import { CONFIDENCE_HELP_TEXT, PDF_EXTRACTION_MESSAGE } from '@/lib/extractionWarnings'

const mockImport = vi.fn()
const mockToast = vi.fn()

vi.mock('@/hooks/useReports', () => ({
  useImportReportIndicators: () => ({
    mutate: mockImport,
    isPending: false,
  }),
}))

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: mockToast }),
}))

function httpError(status: number, detail: unknown) {
  return new AxiosError('Request failed', String(status), undefined, undefined, {
    status,
    data: { detail },
  } as AxiosResponse)
}

const BASE_PREVIEW: ExtractionPreview = {
  report_id: 'rep-1',
  sources: [
    {
      kind: 'content',
      filename: null,
      content_type: null,
      status: 'extracted',
      reason: null,
    },
  ],
  candidates: [
    {
      type: 'domain-name',
      value: 'evil.example',
      original: 'evil.example',
      context: 'contact evil.example for help',
      occurrences: 1,
      defanged: false,
      status: 'new',
      existing_observable_id: null,
      existing_confidence: null,
      already_attributed: false,
      allowlisted: false,
      allowlist_matches: [],
      warnings: [],
    },
    {
      type: 'url',
      value: 'https://evil.example/path',
      original: 'hxxps://evil[.]example/path',
      context: 'visit hxxps://evil[.]example/path now',
      occurrences: 1,
      defanged: true,
      status: 'existing',
      existing_observable_id: 'obs-1',
      existing_confidence: 80,
      already_attributed: false,
      allowlisted: false,
      allowlist_matches: [],
      warnings: [],
    },
    {
      type: 'ip-addr',
      value: '8.8.8.8',
      original: '8.8.8.8',
      context: 'dns 8.8.8.8',
      occurrences: 1,
      defanged: false,
      status: 'existing',
      existing_observable_id: 'obs-2',
      existing_confidence: 90,
      already_attributed: true,
      allowlisted: false,
      allowlist_matches: [],
      warnings: [],
    },
    {
      type: 'domain-name',
      value: 'safe.internal',
      original: 'safe.internal',
      context: 'safe.internal',
      occurrences: 1,
      defanged: false,
      status: 'new',
      existing_observable_id: null,
      existing_confidence: null,
      already_attributed: false,
      allowlisted: true,
      allowlist_matches: ['safe.internal'],
      warnings: [],
    },
    {
      type: 'ip-addr',
      value: '999.1.1.1',
      original: '999.1.1.1',
      context: 'bad 999.1.1.1',
      occurrences: 1,
      defanged: false,
      status: 'invalid',
      existing_observable_id: null,
      existing_confidence: null,
      already_attributed: false,
      allowlisted: false,
      allowlist_matches: [],
      warnings: ['invalid_ip'],
    },
  ],
  truncated: false,
  counts: { total: 5, new: 2, existing: 2, invalid: 1 },
}

function renderReview(preview: ExtractionPreview = BASE_PREVIEW) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <IndicatorImportReview open preview={preview} onClose={vi.fn()} />
    </QueryClientProvider>,
  )
}

function checkboxFor(type: string, value: string): HTMLInputElement {
  return screen.getByRole('checkbox', { name: `Select ${type} ${value}` }) as HTMLInputElement
}

afterEach(() => {
  cleanup()
  mockImport.mockReset()
  mockToast.mockReset()
})

describe('IndicatorImportReview', () => {
  it('applies default selection rules and disables invalid rows', () => {
    renderReview()

    expect(checkboxFor('domain-name', 'evil.example').checked).toBe(true)
    expect(checkboxFor('url', 'https://evil.example/path').checked).toBe(true)
    expect(checkboxFor('ip-addr', '8.8.8.8').checked).toBe(false)
    expect(checkboxFor('domain-name', 'safe.internal').checked).toBe(false)
    expect(checkboxFor('ip-addr', '999.1.1.1').checked).toBe(false)
    expect(checkboxFor('ip-addr', '999.1.1.1').disabled).toBe(true)
  })

  it('defaults confidence to 50 with contract help text', () => {
    renderReview()
    const input = screen.getByLabelText('Confidence for new observables') as HTMLInputElement
    expect(input.value).toBe('50')
    expect(screen.getByText(CONFIDENCE_HELP_TEXT)).toBeTruthy()
  })

  it('does not call import until confirm and sends selected items with confidence', () => {
    renderReview()

    expect(mockImport).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Import 2 indicators' }))

    expect(mockImport).toHaveBeenCalledTimes(1)
    const [args, options] = mockImport.mock.calls[0]
    expect(args).toEqual({
      reportId: 'rep-1',
      payload: {
        confidence: 50,
        items: [
          { type: 'domain-name', value: 'evil.example' },
          { type: 'url', value: 'https://evil.example/path' },
        ],
      },
    })
    expect(options).toEqual(expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) }))
  })

  it('disables import when nothing is selected', () => {
    renderReview()
    fireEvent.click(screen.getByRole('button', { name: 'Select none' }))
    const btn = screen.getByRole('button', { name: 'Import 0 indicators' }) as HTMLButtonElement
    expect(btn.disabled).toBe(true)
  })

  it('shows 422 detail and keeps selection', () => {
    renderReview()
    mockImport.mockImplementation((_args, options) => {
      options?.onError?.(httpError(422, 'Item not_a_candidate: evil.example'))
    })

    fireEvent.click(screen.getByRole('button', { name: 'Import 2 indicators' }))

    expect(screen.getByRole('alert').textContent).toContain('Item not_a_candidate: evil.example')
    expect(checkboxFor('domain-name', 'evil.example').checked).toBe(true)
    expect(checkboxFor('url', 'https://evil.example/path').checked).toBe(true)
  })

  it('shows unsupported PDF message in source list', () => {
    const preview: ExtractionPreview = {
      ...BASE_PREVIEW,
      sources: [
        {
          kind: 'attachment',
          filename: 'scan.pdf',
          content_type: 'application/pdf',
          status: 'unsupported',
          reason: 'pdf_text_extraction_unavailable',
        },
      ],
      candidates: [],
    }
    renderReview(preview)
    expect(screen.getAllByText(PDF_EXTRACTION_MESSAGE).length).toBeGreaterThanOrEqual(1)
  })

  it('renders extracted URL values as plain text, not links', () => {
    renderReview()
    expect(screen.getByText('https://evil.example/path')).toBeTruthy()
    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    const anchors = within(dialog).queryAllByRole('link')
    expect(anchors.length).toBe(0)
  })
})
