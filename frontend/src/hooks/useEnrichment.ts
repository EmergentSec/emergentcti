import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getProviders,
  getEnrichmentConfigs,
  updateEnrichmentConfig,
  triggerEnrichment,
  getEnrichmentHistory,
} from '@/api/enrichment';
import type { EnrichmentConfigUpdate } from '@/types/enrichment';

export function useProviders() {
  return useQuery({
    queryKey: ['enrichment', 'providers'],
    queryFn: getProviders,
    staleTime: 30_000,
  });
}

export function useEnrichmentConfigs() {
  return useQuery({
    queryKey: ['enrichment', 'configs'],
    queryFn: getEnrichmentConfigs,
    staleTime: 30_000,
  });
}

export function useEnrichmentHistory(observableId: string) {
  return useQuery({
    queryKey: ['observables', observableId, 'enrichments'],
    queryFn: () => getEnrichmentHistory(observableId),
    enabled: !!observableId,
    staleTime: 15_000,
  });
}

export function useTriggerEnrichment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      observableId,
      providerName,
    }: {
      observableId: string;
      providerName?: string;
    }) => triggerEnrichment(observableId, providerName),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['observables', variables.observableId, 'enrichments'],
      });
    },
  });
}

export function useUpdateEnrichmentConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      name,
      data,
    }: {
      name: string;
      data: EnrichmentConfigUpdate;
    }) => updateEnrichmentConfig(name, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['enrichment'] });
    },
  });
}
