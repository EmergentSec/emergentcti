import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useCreateObservable, useDeleteObservable } from './useObservables'

vi.mock('@/api/observables', () => ({
  createObservable: vi.fn(() => Promise.resolve({ id: 'obs-1' })),
  deleteObservable: vi.fn(() => Promise.resolve()),
}))

function setup() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { invalidateSpy, wrapper }
}

describe('observable mutations refresh dashboard counts', () => {
  it('create invalidates observables and dashboard', async () => {
    const { invalidateSpy, wrapper } = setup()
    const { result } = renderHook(() => useCreateObservable(), { wrapper })
    result.current.mutate({ type: 'domain-name', value: 'x.example', confidence_score: 50 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['observables'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['dashboard'] })
  })

  it('delete invalidates observables and dashboard', async () => {
    const { invalidateSpy, wrapper } = setup()
    const { result } = renderHook(() => useDeleteObservable(), { wrapper })
    result.current.mutate('obs-1')
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['observables'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['dashboard'] })
  })
})
