import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosError, type AxiosResponse } from 'axios'
import { IndicatorImportReview } from './IndicatorImportReview'
import type { ExtractionPreview } from '@/types/reportIocExtraction'
import {
  CONFIDENCE_HELP_TEXT,
  EXPORT_ELIGIBILITY_NOTICE,
  PDF_EXTRACTION_MESSAGE,
} from '@/lib/extractionWarnings'
import {
  IMPORT_CLOSE_UNLOCK_MS,
  IMPORT_PENDING_UNLOCKED_MESSAGE,
  IMPORT_STILL_RUNNING_MESSAGE,
  IMPORT_TIMEOUT_MESSAGE,
  importPendingLockedMessage,
} from '@/lib/importRequest'

const mockImport = vi.fn()
const mockToast = vi.fn()
let mockIsPending = false

vi.mock('@/hooks/useReports', () => ({
  useImportReportIndicators: () => ({
    mutate: mockImport,
    isPending: mockIsPending,
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

/** Mirrors react-query: invoke onSettled after onSuccess/onError like production. */
function invokeMutate(
  impl: (
    args: unknown,
    options: {
      onSuccess?: (result: unknown) => void
      onError?: (err: unknown) => void
      onSettled?: () => void
    },
  ) => void,
) {
  mockImport.mockImplementation((args, options) => {
    impl(args, options ?? {})
    options?.onSettled?.()
  })
}

const PINNED_422_DETAIL = [
  {
    type: 'greater_than_equal',
    loc: ['body', 'confidence'],
    msg: 'Input should be greater than or equal to 0',
    input: -1,
  },
  {
    type: 'not_a_candidate',
    loc: ['body', 'items'],
    msg: '2 item(s) are not valid candidates extracted from this report: url http://x, domain-name bad',
    items: [
      { index: 0, type: 'url', value: 'https://evil.example/path' },
      { index: 1, type: 'domain-name', value: 'evil.example' },
    ],
  },
]

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

function renderReview(preview: ExtractionPreview = BASE_PREVIEW, onClose = vi.fn<() => void>()) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return {
    onClose,
    ...render(
      <QueryClientProvider client={client}>
        <IndicatorImportReview open preview={preview} onClose={onClose} />
      </QueryClientProvider>,
    ),
  }
}

function checkboxFor(type: string, value: string): HTMLInputElement {
  return screen.getByRole('checkbox', { name: `Select ${type} ${value}` }) as HTMLInputElement
}

function confidenceInput(): HTMLInputElement {
  return screen.getByLabelText('Confidence for new observables') as HTMLInputElement
}

function importButton(): HTMLButtonElement {
  return screen.getByRole('button', { name: /^Import \d+ indicator/ }) as HTMLButtonElement
}

afterEach(() => {
  cleanup()
  mockImport.mockReset()
  mockToast.mockReset()
  mockIsPending = false
  vi.useRealTimers()
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
    expect(confidenceInput().value).toBe('50')
    expect(screen.getByText(CONFIDENCE_HELP_TEXT)).toBeTruthy()
  })

  it('shows export eligibility notice', () => {
    renderReview()
    expect(screen.getByText(EXPORT_ELIGIBILITY_NOTICE)).toBeTruthy()
  })

  it('does not call import until confirm and sends selected items with confidence', () => {
    renderReview()

    expect(mockImport).not.toHaveBeenCalled()

    fireEvent.click(importButton())

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
    expect(importButton().disabled).toBe(true)
  })

  it('select all selects only selectable rows including already-attributed existing', () => {
    renderReview()
    fireEvent.click(screen.getByRole('button', { name: 'Select none' }))
    fireEvent.click(screen.getByRole('button', { name: 'Select all' }))

    expect(checkboxFor('domain-name', 'evil.example').checked).toBe(true)
    expect(checkboxFor('url', 'https://evil.example/path').checked).toBe(true)
    expect(checkboxFor('ip-addr', '8.8.8.8').checked).toBe(true)
    expect(checkboxFor('domain-name', 'safe.internal').checked).toBe(true)
    expect(checkboxFor('ip-addr', '999.1.1.1').checked).toBe(false)
  })

  it('allows toggling a selected row off', () => {
    renderReview()
    expect(checkboxFor('domain-name', 'evil.example').checked).toBe(true)
    fireEvent.click(checkboxFor('domain-name', 'evil.example'))
    expect(checkboxFor('domain-name', 'evil.example').checked).toBe(false)
  })

  it.each(['', '101', '-1', '50.5'])('rejects invalid confidence %j', (value) => {
    renderReview()
    fireEvent.change(confidenceInput(), { target: { value } })
    expect(screen.getByText('Enter a whole number from 0 to 100')).toBeTruthy()
    expect(importButton().disabled).toBe(true)
    fireEvent.click(importButton())
    expect(mockImport).not.toHaveBeenCalled()
  })

  it('shows string 422 detail and keeps selection', () => {
    renderReview()
    invokeMutate((_args, options) => {
      options?.onError?.(httpError(422, 'Item not_a_candidate: evil.example'))
    })

    fireEvent.click(importButton())

    expect(screen.getByRole('alert').textContent).toContain('Item not_a_candidate: evil.example')
    expect(checkboxFor('domain-name', 'evil.example').checked).toBe(true)
    expect(checkboxFor('url', 'https://evil.example/path').checked).toBe(true)
  })

  it('shows every pinned 422 msg and highlights not_a_candidate rows', () => {
    renderReview()
    invokeMutate((_args, options) => {
      options?.onError?.(httpError(422, PINNED_422_DETAIL))
    })

    fireEvent.click(importButton())

    const alert = screen.getByRole('alert')
    expect(alert.textContent).toContain('Input should be greater than or equal to 0')
    expect(alert.textContent).toContain(
      '2 item(s) are not valid candidates extracted from this report: url http://x, domain-name bad',
    )

    expect(screen.getByTestId('candidate-row-domain-name\0evil.example').className).toContain(
      'bg-destructive-soft',
    )
    expect(screen.getByTestId('candidate-row-url\0https://evil.example/path').className).toContain(
      'bg-destructive-soft',
    )
  })

  it('shows server detail for non-422 import errors', () => {
    renderReview()
    invokeMutate((_args, options) => {
      options?.onError?.(httpError(404, 'Report not found'))
    })

    fireEvent.click(importButton())

    expect(screen.getByRole('alert').textContent).toBe('Report not found')
  })

  it('clears 422 alert only when no highlighted rows remain after toggling', () => {
    renderReview()
    invokeMutate((_args, options) => {
      options?.onError?.(httpError(422, PINNED_422_DETAIL))
    })
    fireEvent.click(importButton())
    expect(screen.getByRole('alert')).toBeTruthy()

    fireEvent.click(checkboxFor('domain-name', 'evil.example'))
    expect(screen.getByRole('alert')).toBeTruthy()
    expect(screen.getByTestId('candidate-row-domain-name\0evil.example').className).not.toContain(
      'bg-destructive-soft',
    )
    expect(screen.getByTestId('candidate-row-url\0https://evil.example/path').className).toContain(
      'bg-destructive-soft',
    )

    fireEvent.click(checkboxFor('url', 'https://evil.example/path'))
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByTestId('candidate-row-url\0https://evil.example/path').className).not.toContain(
      'bg-destructive-soft',
    )
  })

  it('closes on success; the import hook reports the counts', () => {
    const onClose = vi.fn()
    renderReview(BASE_PREVIEW, onClose)
    invokeMutate((_args, options) => {
      options?.onSuccess?.({ created: 2, attributed_existing: 0, already_attributed: 1, observables: [] })
    })

    fireEvent.click(importButton())

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(mockToast).not.toHaveBeenCalled()
  })

  it('shows a retry-safe alert when the import request times out', () => {
    renderReview()
    invokeMutate((_args, options) => {
      options?.onError?.(new AxiosError('timeout of 60000ms exceeded', 'ECONNABORTED'))
    })

    fireEvent.click(importButton())

    expect(screen.getByRole('alert').textContent).toBe(IMPORT_TIMEOUT_MESSAGE)
    expect((screen.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByRole('button', { name: 'Close' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('shows pending import state and renders close disabled while blocked', () => {
    mockIsPending = true
    renderReview()
    const pendingBtn = screen.getByRole('button', { name: 'Importing…' }) as HTMLButtonElement
    expect(pendingBtn).toBeTruthy()
    expect(pendingBtn.disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement).disabled).toBe(true)
    const close = screen.getByRole('button', { name: 'Close' }) as HTMLButtonElement
    expect(close.disabled).toBe(true)
    expect(close.className).toContain('disabled:opacity-50')
    expect(screen.getByRole('status').textContent).toBe(importPendingLockedMessage())
  })

  it('ignores Escape, overlay, and close while import is blocked', () => {
    const onClose = vi.fn()
    mockIsPending = true
    renderReview(BASE_PREVIEW, onClose)
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    const overlay = document.querySelector('.bg-overlay')
    expect(overlay).toBeTruthy()
    fireEvent.click(overlay!)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('allows close after the lock and says the result will still be reported', () => {
    vi.useFakeTimers()
    const onClose = vi.fn()
    mockIsPending = true
    renderReview(BASE_PREVIEW, onClose)

    act(() => {
      vi.advanceTimersByTime(IMPORT_CLOSE_UNLOCK_MS - 1)
    })
    expect((screen.getByRole('button', { name: 'Close' }) as HTMLButtonElement).disabled).toBe(true)
    expect(onClose).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(1)
    })

    expect(screen.getByRole('status').textContent).toBe(IMPORT_PENDING_UNLOCKED_MESSAGE)
    expect((screen.getByRole('button', { name: 'Close' }) as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement).disabled).toBe(false)

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(mockToast).toHaveBeenCalledWith(IMPORT_STILL_RUNNING_MESSAGE, 'info')
  })

  it('ignores a second confirm click before the mutation settles', () => {
    renderReview()
    mockImport.mockImplementation(() => {
      /* hang until test ends */
    })

    fireEvent.click(importButton())
    fireEvent.click(importButton())

    expect(mockImport).toHaveBeenCalledTimes(1)
  })

  it('shows PDF notice once with unsupported status in source list', () => {
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
    expect(screen.getByText('Unsupported (PDF)')).toBeTruthy()
    expect(screen.getAllByText(PDF_EXTRACTION_MESSAGE)).toHaveLength(1)
  })

  it('renders extracted URL values as plain text, not links', () => {
    renderReview()
    expect(screen.getByText('https://evil.example/path')).toBeTruthy()
    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    const anchors = within(dialog).queryAllByRole('link')
    expect(anchors.length).toBe(0)
  })
})
