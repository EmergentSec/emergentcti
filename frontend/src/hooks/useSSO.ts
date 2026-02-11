import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSSOProviders,
  getSSOConfigs,
  updateSSOConfig,
  deleteSSOConfig,
} from '@/api/sso';
import type { SSOProviderConfigUpdate } from '@/types/sso';

export function useSSOProviders() {
  return useQuery({
    queryKey: ['sso', 'providers'],
    queryFn: getSSOProviders,
    staleTime: 30_000,
  });
}

export function useSSOConfigs() {
  return useQuery({
    queryKey: ['sso', 'configs'],
    queryFn: getSSOConfigs,
    staleTime: 30_000,
  });
}

export function useUpdateSSOConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      providerType,
      data,
    }: {
      providerType: string;
      data: SSOProviderConfigUpdate;
    }) => updateSSOConfig(providerType, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sso'] });
    },
  });
}

export function useDeleteSSOConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (providerType: string) => deleteSSOConfig(providerType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sso'] });
    },
  });
}
