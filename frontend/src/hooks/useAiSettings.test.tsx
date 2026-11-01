import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as aiApi from '@/api/ai'
import { aiModelsKey, aiSettingsKey, useRemoveAiProvider, useSaveAiKey } from './useAiSettings'
import type { AiModelList } from '@/types/ai'

vi.mock('@/api/ai', () => ({
  getAiSettings: vi.fn(),
  putAiProviderKey: vi.fn(),
  deleteAiProvider: vi.fn(),
  checkAiProvider: vi.fn(),
  getAiModels: vi.fn(),
  runAiInferenceTest: vi.fn(),
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
