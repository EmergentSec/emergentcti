import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useCreateObservable, useDeleteObservable, useSetConfidenceOverride, useClearConfidenceOverride } from './useObservables'

vi.mock('@/api/observables', () => ({
  createObservable: vi.fn(() => Promise.resolve({ id: 'obs-1' })),
  deleteObservable: vi.fn(() => Promise.resolve()),
  setConfidenceOverride: vi.fn(() => Promise.resolve({ id: 'obs-1' })),
  clearConfidenceOverride: vi.fn(() => Promise.resolve({ id: 'obs-1' })),
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

  it('set confidence override invalidates observable, observables, and dashboard', async () => {
    const { invalidateSpy, wrapper } = setup()
    const { result } = renderHook(() => useSetConfidenceOverride(), { wrapper })
    result.current.mutate({ id: 'obs-1', confidence: 80 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['observable', 'obs-1'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['observables'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['dashboard'] })
  })

  it('clear confidence override invalidates observable, observables, and dashboard', async () => {
    const { invalidateSpy, wrapper } = setup()
    const { result } = renderHook(() => useClearConfidenceOverride(), { wrapper })
    result.current.mutate('obs-1')
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['observable', 'obs-1'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['observables'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['dashboard'] })
  })
})
