import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getTactics,
  getTechniques,
  getHeatmap,
  syncAttackData,
  getObservableTechniques,
  mapObservableTechnique,
  unmapObservableTechnique,
} from '@/api/attack';

export function useTactics() {
  return useQuery({
    queryKey: ['attack', 'tactics'],
    queryFn: getTactics,
    staleTime: 60_000,
  });
}

export function useTechniques(tacticId?: string) {
  return useQuery({
    queryKey: ['attack', 'techniques', tacticId],
    queryFn: () => getTechniques(tacticId),
    staleTime: 60_000,
  });
}

export function useHeatmap() {
  return useQuery({
    queryKey: ['attack', 'heatmap'],
    queryFn: getHeatmap,
    staleTime: 30_000,
  });
}

export function useSyncAttackData() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: syncAttackData,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['attack'] });
    },
  });
}

export function useObservableTechniques(observableId: string) {
  return useQuery({
    queryKey: ['attack', 'observables', observableId, 'techniques'],
    queryFn: () => getObservableTechniques(observableId),
    enabled: !!observableId,
    staleTime: 30_000,
  });
}

export function useMapTechnique() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      observableId,
      techniqueId,
    }: {
      observableId: string;
      techniqueId: string;
    }) => mapObservableTechnique(observableId, techniqueId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['attack', 'observables', variables.observableId, 'techniques'],
      });
      queryClient.invalidateQueries({ queryKey: ['attack', 'heatmap'] });
    },
  });
}

export function useUnmapTechnique() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      observableId,
      techniqueId,
    }: {
      observableId: string;
      techniqueId: string;
    }) => unmapObservableTechnique(observableId, techniqueId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['attack', 'observables', variables.observableId, 'techniques'],
      });
      queryClient.invalidateQueries({ queryKey: ['attack', 'heatmap'] });
    },
  });
}
