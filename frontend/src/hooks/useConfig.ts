import { useQuery } from '@tanstack/react-query'
import { getConfig } from '@/api/settings'
import type { ConfidenceDecayConfig } from '@/types/settings'

export function useConfig() {
  return useQuery<ConfidenceDecayConfig>({
    queryKey: ['config'],
    queryFn: getConfig,
  })
}
