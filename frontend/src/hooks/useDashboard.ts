import { useQuery } from '@tanstack/react-query'
import { getStats } from '@/api/dashboard'

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: getStats,
    refetchInterval: 60_000, // Auto-refresh every 60s
  })
}
