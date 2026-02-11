import { useQuery } from '@tanstack/react-query';
import { fetchGraph, type GraphFilters } from '@/api/graph';

export function useGraph(
  entityType: string,
  entityId: string,
  depth: number = 2,
  filters?: GraphFilters
) {
  return useQuery({
    queryKey: ['graph', entityType, entityId, depth, filters],
    queryFn: () => fetchGraph(entityType, entityId, depth, filters),
    enabled: !!entityId && !!entityType,
    staleTime: 30_000,
  });
}
