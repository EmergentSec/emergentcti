import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import {
  deleteAiPricingRow,
  getAiInferenceTestPreview,
  getAiPricing,
  getAiUsage,
  getAiUsagePolicy,
  getAiUsageRecords,
  putAiPricingRow,
  putAiUsagePolicy,
} from '@/api/ai'
import type { AiProvider, AiUsagePolicy } from '@/types/ai'

export const aiUsageKey = (month: string) => ['ai-usage', month] as const
export const aiUsageRecordsKey = (month: string) => ['ai-usage-records', month] as const
export const aiUsagePolicyKey = ['ai-usage-policy'] as const
export const aiPricingKey = ['ai-pricing'] as const
export const aiInferencePreviewKey = (provider: AiProvider, model: string) =>
  ['ai-inference-preview', provider, model] as const

export function useAiUsage(month: string) {
  return useQuery({ queryKey: aiUsageKey(month), queryFn: () => getAiUsage(month) })
}

export const AI_USAGE_RECORDS_PAGE = 50

/** Newest-first records for `month`, paged with the backend's `before` cursor. */
export function useAiUsageRecords(month: string) {
  return useInfiniteQuery({
    queryKey: aiUsageRecordsKey(month),
    queryFn: ({ pageParam }) => getAiUsageRecords(month, AI_USAGE_RECORDS_PAGE, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_before ?? undefined,
  })
}

/**
 * Anything that can change spend, budget, pricing or the policy decision makes
 * the usage report, the records and every cached inference preview stale.
 */
export function invalidateAiSpendQueries(queryClient: QueryClient) {
  queryClient.invalidateQueries({ queryKey: ['ai-usage'] })
  queryClient.invalidateQueries({ queryKey: ['ai-usage-records'] })
  queryClient.invalidateQueries({ queryKey: ['ai-inference-preview'] })
}

export function useAiUsagePolicy() {
  return useQuery({ queryKey: aiUsagePolicyKey, queryFn: getAiUsagePolicy })
}

export function useSaveAiUsagePolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: Omit<AiUsagePolicy, 'updated_at' | 'guarantee'>) => putAiUsagePolicy(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aiUsagePolicyKey })
      invalidateAiSpendQueries(queryClient)
    },
  })
}

export function useAiPricing() {
  return useQuery({ queryKey: aiPricingKey, queryFn: getAiPricing })
}

export function useSaveAiPricingRow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      provider,
      model,
      input_usd_per_mtok,
      output_usd_per_mtok,
    }: {
      provider: AiProvider
      model: string
      input_usd_per_mtok: string
      output_usd_per_mtok: string
    }) => putAiPricingRow(provider, model, { input_usd_per_mtok, output_usd_per_mtok }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aiPricingKey })
      queryClient.invalidateQueries({ queryKey: ['ai-inference-preview'] })
    },
  })
}

export function useDeleteAiPricingRow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ provider, model }: { provider: AiProvider; model: string }) => deleteAiPricingRow(provider, model),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aiPricingKey })
      queryClient.invalidateQueries({ queryKey: ['ai-inference-preview'] })
    },
  })
}

export function useAiInferenceTestPreview(provider: AiProvider | null, model: string, enabled: boolean) {
  return useQuery({
    queryKey: provider ? aiInferencePreviewKey(provider, model) : ['ai-inference-preview', 'none'],
    queryFn: () => getAiInferenceTestPreview(provider!, model),
    enabled: enabled && !!provider && model.trim() !== '',
    retry: false,
    // The decision depends on live budget/policy state: always refetch on open.
    staleTime: 0,
  })
}
