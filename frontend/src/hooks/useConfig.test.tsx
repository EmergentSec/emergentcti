import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useConfig } from './useConfig'

vi.mock('@/api/settings', () => ({
  getConfig: vi.fn().mockResolvedValue({
    confidence_decay_enabled: true,
    confidence_decay_days: 30,
    confidence_decay_rate: 5,
    confidence_decay_floor: 10,
    confidence_decay_interval_hours: 24,
  }),
}))

afterEach(cleanup)

describe('useConfig', () => {
  it('fetches config and exposes decay settings', async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(() => useConfig(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.confidence_decay_days).toBe(30)
    expect(result.current.data?.confidence_decay_rate).toBe(5)
    expect(result.current.data?.confidence_decay_floor).toBe(10)
    expect(result.current.data?.confidence_decay_enabled).toBe(true)
  })

  it('uses queryKey ["config"]', async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(() => useConfig(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Verify the data is cached under the ['config'] key
    const cached = client.getQueryData(['config'])
    expect(cached).toBeDefined()
  })
})
