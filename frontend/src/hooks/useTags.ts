import { useQuery } from '@tanstack/react-query'
import { getTags } from '@/api/tags'

export function useTags(q?: string) {
  return useQuery({
    queryKey: ['tags', q ?? ''],
    queryFn: () => getTags(q),
  })
}
