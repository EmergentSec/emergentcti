import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as aiApi from '@/api/ai'
import { aiModelsKey, aiSettingsKey, useAiInferenceTest, useRemoveAiProvider, useSaveAiKey } from './useAiSettings'
import {
  aiInferencePreviewKey,
  aiPricingKey,
  aiUsageKey,
  aiUsagePolicyKey,
  aiUsageRecordsKey,
  useDeleteAiPricingRow,
  useSaveAiPricingRow,
  useSaveAiUsagePolicy,
} from './useAiUsage'
import { usagePolicy, usageReport } from '@/test/fixtures/ai'
import type { AiModelList } from '@/types/ai'

vi.mock('@/api/ai', () => ({
  getAiSettings: vi.fn(),
  putAiProviderKey: vi.fn(),
  deleteAiProvider: vi.fn(),
  checkAiProvider: vi.fn(),
  getAiModels: vi.fn(),
  runAiInferenceTest: vi.fn(),
  putAiUsagePolicy: vi.fn(),
  putAiPricingRow: vi.fn(),
  deleteAiPricingRow: vi.fn(),
  putAiDefault: vi.fn(),
  deleteAiDefault: vi.fn(),
}))

const api = vi.mocked(aiApi)
const FAKE_KEY = 'sk-test-not-a-real-key-0000'

function modelList(provider: AiModelList['provider']): AiModelList {
  return { provider, source: 'cache', fetched_at: null, error: null, models: [{ id: 'm', name: 'm' }] }
}

/** Real QueryClient seeded with settings and two providers' model lists. */
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  client.setQueryData(aiSettingsKey, { providers: [], default: null })
  client.setQueryData(aiModelsKey('openai'), modelList('openai'))
  client.setQueryData(aiModelsKey('anthropic'), modelList('anthropic'))
  const invalidate = vi.spyOn(client, 'invalidateQueries')
  const remove = vi.spyOn(client, 'removeQueries')
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, invalidate, remove, wrapper }
}

const invalidated = (client: QueryClient, key: readonly unknown[]) => client.getQueryState(key)?.isInvalidated

beforeEach(() => {
  vi.clearAllMocks()
  api.getAiSettings.mockResolvedValue({ providers: [], default: null })
})

afterEach(cleanup)

describe('useSaveAiKey', () => {
  it('invalidates settings and exactly that provider’s model list', async () => {
    api.putAiProviderKey.mockResolvedValue({} as never)
    const { client, invalidate, wrapper } = setup()
    const { result } = renderHook(() => useSaveAiKey(), { wrapper })

    await act(() => result.current.mutateAsync({ provider: 'openai', apiKey: FAKE_KEY }))

    expect(api.putAiProviderKey).toHaveBeenCalledWith('openai', FAKE_KEY)
    expect(invalidate.mock.calls.map(([filters]) => filters?.queryKey)).toEqual([aiSettingsKey, aiModelsKey('openai')])
    expect(invalidated(client, aiSettingsKey)).toBe(true)
    expect(invalidated(client, aiModelsKey('openai'))).toBe(true)
    expect(invalidated(client, aiModelsKey('anthropic'))).toBe(false)
  })

  // gcTime: 0 evicts a settled mutation as soon as no observer holds it: after the
  // documented caller reset() (what AiSettings does in onSettled) or on unmount.
  it('evicts the settled key mutation from the mutation cache once the caller resets', async () => {
    api.putAiProviderKey.mockResolvedValue({} as never)
    const { client, wrapper } = setup()
    const { result } = renderHook(() => useSaveAiKey(), { wrapper })

    await act(() => result.current.mutateAsync({ provider: 'openai', apiKey: FAKE_KEY }))
    act(() => result.current.reset())

    await waitFor(() => expect(client.getMutationCache().getAll()).toHaveLength(0))
    expect(result.current.variables).toBeUndefined()
    const queryKeys = client.getQueryCache().getAll().map((q) => q.queryKey)
    expect(JSON.stringify(queryKeys)).not.toContain(FAKE_KEY)
  })

  it('evicts a failed key mutation when the hook unmounts', async () => {
    api.putAiProviderKey.mockRejectedValue(new Error('nope'))
    const { client, invalidate, wrapper } = setup()
    const { result, unmount } = renderHook(() => useSaveAiKey(), { wrapper })

    await act(() => result.current.mutateAsync({ provider: 'openai', apiKey: FAKE_KEY }).catch(() => undefined))
    expect(invalidate).not.toHaveBeenCalled()
    unmount()

    await waitFor(() => expect(client.getMutationCache().getAll()).toHaveLength(0))
  })
})

describe('useRemoveAiProvider', () => {
  it('invalidates settings and removes exactly that provider’s model list', async () => {
    api.deleteAiProvider.mockResolvedValue(undefined)
    const { client, invalidate, remove, wrapper } = setup()
    const { result } = renderHook(() => useRemoveAiProvider(), { wrapper })

    await act(() => result.current.mutateAsync('openai'))

    expect(api.deleteAiProvider).toHaveBeenCalledWith('openai')
    expect(invalidate.mock.calls.map(([filters]) => filters?.queryKey)).toEqual([aiSettingsKey])
    expect(remove.mock.calls.map(([filters]) => filters?.queryKey)).toEqual([aiModelsKey('openai')])
    expect(invalidated(client, aiSettingsKey)).toBe(true)
    expect(client.getQueryCache().find({ queryKey: aiModelsKey('openai'), exact: true })).toBeUndefined()
    expect(client.getQueryData(aiModelsKey('anthropic'))).toEqual(modelList('anthropic'))
    expect(invalidated(client, aiModelsKey('anthropic'))).toBe(false)
  })
})

/** Seeds usage, records and a preview so invalidation is observable per key. */
function seedSpend(client: QueryClient) {
  client.setQueryData(aiUsageKey('2026-11'), usageReport())
  client.setQueryData(aiUsageRecordsKey('2026-11'), { pages: [{ items: [], next_before: null }], pageParams: [undefined] })
  client.setQueryData(aiInferencePreviewKey('anthropic', 'm'), {})
  client.setQueryData(aiPricingKey, { items: [] })
  client.setQueryData(aiUsagePolicyKey, usagePolicy())
}

describe('spend-affecting mutations refresh usage, records and previews (M4, M5)', () => {
  it('an inference test invalidates usage, records and previews, even when it fails', async () => {
    for (const outcome of ['ok', 'error'] as const) {
      if (outcome === 'ok') {
        api.runAiInferenceTest.mockResolvedValue({ ok: true, error: null, latency_ms: 1, usage: null })
      } else {
        api.runAiInferenceTest.mockRejectedValue(new Error('boom'))
      }
      const { client, wrapper } = setup()
      seedSpend(client)
      const { result } = renderHook(() => useAiInferenceTest(), { wrapper })
      await act(async () => {
        await result.current.mutateAsync({ provider: 'anthropic', model: 'm' }).catch(() => {})
      })
      await waitFor(() => expect(invalidated(client, aiUsageKey('2026-11'))).toBe(true))
      expect(invalidated(client, aiUsageRecordsKey('2026-11'))).toBe(true)
      expect(invalidated(client, aiInferencePreviewKey('anthropic', 'm'))).toBe(true)
      expect(invalidated(client, aiPricingKey)).toBe(false)
    }
  })

  it('saving the policy invalidates usage, records and previews', async () => {
    api.putAiUsagePolicy.mockResolvedValue(usagePolicy())
    const { client, wrapper } = setup()
    seedSpend(client)
    const { result } = renderHook(() => useSaveAiUsagePolicy(), { wrapper })
    const { updated_at: _u, guarantee: _g, ...body } = usagePolicy()
    await act(() => result.current.mutateAsync(body))
    expect(invalidated(client, aiUsagePolicyKey)).toBe(true)
    expect(invalidated(client, aiUsageKey('2026-11'))).toBe(true)
    expect(invalidated(client, aiUsageRecordsKey('2026-11'))).toBe(true)
    expect(invalidated(client, aiInferencePreviewKey('anthropic', 'm'))).toBe(true)
  })

  it('saving or deleting pricing invalidates previews', async () => {
    api.putAiPricingRow.mockResolvedValue({} as never)
    api.deleteAiPricingRow.mockResolvedValue(undefined)
    for (const which of ['save', 'delete'] as const) {
      const { client, wrapper } = setup()
      seedSpend(client)
      if (which === 'save') {
        const { result } = renderHook(() => useSaveAiPricingRow(), { wrapper })
        await act(() =>
          result.current.mutateAsync({ provider: 'anthropic', model: 'm', input_usd_per_mtok: '1', output_usd_per_mtok: '2' }),
        )
      } else {
        const { result } = renderHook(() => useDeleteAiPricingRow(), { wrapper })
        await act(() => result.current.mutateAsync({ provider: 'anthropic', model: 'm' }))
      }
      expect(invalidated(client, aiPricingKey)).toBe(true)
      expect(invalidated(client, aiInferencePreviewKey('anthropic', 'm'))).toBe(true)
    }
  })
})
