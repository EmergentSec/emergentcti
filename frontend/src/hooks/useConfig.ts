import { useQuery } from '@tanstack/react-query'
import { getConfig } from '@/api/settings'

export function useConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
  })
}
