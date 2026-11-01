import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useImportReportIndicators } from './useReports'

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
  })
})
