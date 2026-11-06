import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosError } from 'axios'
import type { ReactNode } from 'react'
import { importReportIndicators } from '@/api/reports'
import {
  IMPORT_TIMEOUT_MESSAGE,
  importSuccessMessage,
  setImportFailureInline,
} from '@/lib/importRequest'
import { useImportReportIndicators } from './useReports'

const mockToast = vi.fn()

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({ toast: mockToast }),
}))

vi.mock('@/api/reports', () => ({
  importReportIndicators: vi.fn(() =>
    Promise.resolve({ created: 1, attributed_existing: 0, already_attributed: 0, observables: [] }),
  ),
}))

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

const SUCCESS = { created: 1, attributed_existing: 0, already_attributed: 0, observables: [] }

afterEach(() => {
  mockToast.mockReset()
  setImportFailureInline(false)
  vi.mocked(importReportIndicators).mockReset()
  vi.mocked(importReportIndicators).mockResolvedValue(SUCCESS)
})

describe('useImportReportIndicators', () => {
  it('invalidates report, observables, and observableReports on success', async () => {
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')

    const { result } = renderHook(() => useImportReportIndicators(), { wrapper: wrapper(client) })

    result.current.mutate({
      reportId: 'rep-1',
      payload: { confidence: 50, items: [{ type: 'domain-name', value: 'x.example' }] },
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['report', 'rep-1'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['observables'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['observableReports'] })
    // Dashboard KPIs and the sidebar observable badge read this query.
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['dashboard'] })
    expect(mockToast).toHaveBeenCalledWith(importSuccessMessage(SUCCESS), 'success')
  })

  it('does not toast a failure while the review dialog is showing it inline', async () => {
    setImportFailureInline(true)
    vi.mocked(importReportIndicators).mockRejectedValue(
      new AxiosError('timeout of 60000ms exceeded', 'ECONNABORTED'),
    )
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    const { result } = renderHook(() => useImportReportIndicators(), { wrapper: wrapper(client) })

    result.current.mutate({
      reportId: 'rep-1',
      payload: { confidence: 50, items: [{ type: 'domain-name', value: 'x.example' }] },
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(mockToast).not.toHaveBeenCalled()
  })

  it('toasts a retry-safe message when a dismissed import times out', async () => {
    setImportFailureInline(false)
    vi.mocked(importReportIndicators).mockRejectedValue(
      new AxiosError('timeout of 60000ms exceeded', 'ECONNABORTED'),
    )
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    const { result } = renderHook(() => useImportReportIndicators(), { wrapper: wrapper(client) })

    result.current.mutate({
      reportId: 'rep-1',
      payload: { confidence: 50, items: [{ type: 'domain-name', value: 'x.example' }] },
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(mockToast).toHaveBeenCalledWith(IMPORT_TIMEOUT_MESSAGE, 'error')
  })

  it('still toasts success after the dialog unmounts during the request', async () => {
    let resolveImport: (value: typeof SUCCESS) => void = () => {}
    vi.mocked(importReportIndicators).mockReturnValue(
      new Promise((resolve) => {
        resolveImport = resolve
      }),
    )
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
    const { result, unmount } = renderHook(() => useImportReportIndicators(), { wrapper: wrapper(client) })

    result.current.mutate({
      reportId: 'rep-1',
      payload: { confidence: 50, items: [{ type: 'domain-name', value: 'x.example' }] },
    })

    setImportFailureInline(false)
    unmount()
    resolveImport(SUCCESS)

    await waitFor(() => expect(mockToast).toHaveBeenCalledWith(importSuccessMessage(SUCCESS), 'success'))
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['report', 'rep-1'] })
  })
})
