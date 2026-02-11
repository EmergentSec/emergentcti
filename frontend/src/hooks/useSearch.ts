import { useQuery } from '@tanstack/react-query';
import { searchObservables } from '@/api/search';
import type { SearchParams } from '@/types/search';

export function useSearch(params: SearchParams) {
  return useQuery({
    queryKey: ['search', params],
    queryFn: () => searchObservables(params),
    enabled: params.q.length > 0,
    staleTime: 30_000,
  });
}
