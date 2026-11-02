import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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

export function useAiUsageRecords(month: string) {
  return useQuery({ queryKey: aiUsageRecordsKey(month), queryFn: () => getAiUsageRecords(month) })
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
      queryClient.invalidateQueries({ queryKey: ['ai-usage'] })
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: aiPricingKey }),
  })
}

export function useDeleteAiPricingRow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ provider, model }: { provider: AiProvider; model: string }) => deleteAiPricingRow(provider, model),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: aiPricingKey }),
  })
}

export function useAiInferenceTestPreview(provider: AiProvider | null, model: string, enabled: boolean) {
  return useQuery({
    queryKey: provider ? aiInferencePreviewKey(provider, model) : ['ai-inference-preview', 'none'],
    queryFn: () => getAiInferenceTestPreview(provider!, model),
    enabled: enabled && !!provider && model.trim() !== '',
    retry: false,
  })
}
