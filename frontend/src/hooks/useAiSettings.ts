import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  checkAiProvider,
  deleteAiDefault,
  deleteAiProvider,
  getAiModels,
  getAiSettings,
  putAiDefault,
  putAiProviderKey,
  runAiInferenceTest,
} from '@/api/ai'
import type { AiDefault, AiProvider } from '@/types/ai'
import { invalidateAiSpendQueries } from './useAiUsage'

export const aiSettingsKey = ['ai-settings'] as const
export const aiModelsKey = (provider: AiProvider) => ['ai-models', provider] as const

export function useAiSettings() {
  return useQuery({ queryKey: aiSettingsKey, queryFn: getAiSettings })
}

/**
 * Model list for one provider (`refresh=false`: served from the backend cache
 * when fresh). Not refetched on focus or retried, so idle page views don't
 * trigger repeated provider calls. Use `useRefreshAiModels` to force a live fetch.
 */
export function useAiModels(provider: AiProvider | null, enabled = true) {
  return useQuery({
    queryKey: provider ? aiModelsKey(provider) : ['ai-models', 'none'],
    queryFn: () => getAiModels(provider!, false),
    enabled: enabled && !!provider,
    retry: false,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  })
}

export function useRefreshAiModels() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (provider: AiProvider) => getAiModels(provider, true),
    onSuccess: (list, provider) => {
      queryClient.setQueryData(aiModelsKey(provider), list)
      queryClient.invalidateQueries({ queryKey: aiSettingsKey })
    },
  })
}

/**
 * Saves a key. `gcTime: 0` drops the settled mutation (whose variables hold the
 * plaintext key) from the mutation cache right away; callers should also
 * `reset()` once they've handled the result.
 */
export function useSaveAiKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ provider, apiKey }: { provider: AiProvider; apiKey: string }) =>
      putAiProviderKey(provider, apiKey),
    gcTime: 0,
    onSuccess: (_status, { provider }) => {
      queryClient.invalidateQueries({ queryKey: aiSettingsKey })
      queryClient.invalidateQueries({ queryKey: aiModelsKey(provider) })
    },
  })
}

export function useRemoveAiProvider() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (provider: AiProvider) => deleteAiProvider(provider),
    onSuccess: (_void, provider) => {
      queryClient.invalidateQueries({ queryKey: aiSettingsKey })
      queryClient.removeQueries({ queryKey: aiModelsKey(provider) })
    },
  })
}

export function useCheckAiConnection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (provider: AiProvider) => checkAiProvider(provider),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: aiSettingsKey })
    },
  })
}

/** Billable. Only call `mutate` from an explicit confirmation. */
export function useAiInferenceTest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ provider, model }: { provider: AiProvider; model: string }) =>
      runAiInferenceTest(provider, model),
    // A test (even a failed one) writes a usage record and moves committed spend.
    onSettled: () => invalidateAiSpendQueries(queryClient),
  })
}

export function useSetAiDefault() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: AiDefault) => putAiDefault(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aiSettingsKey })
    },
  })
}

export function useClearAiDefault() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => deleteAiDefault(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aiSettingsKey })
    },
  })
}
