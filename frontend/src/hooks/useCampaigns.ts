import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getCampaigns,
  getCampaign,
  createCampaign,
  updateCampaign,
  deleteCampaign,
  linkCampaignObservable,
  unlinkCampaignObservable,
  getCampaignTimeline,
  getCampaignsForObservable,
} from '@/api/campaigns';
import type {
  CampaignFilters,
  CampaignCreateRequest,
  CampaignUpdateRequest,
} from '@/types/campaign';

export function useCampaigns(filters: CampaignFilters = {}) {
  return useQuery({
    queryKey: ['campaigns', filters],
    queryFn: () => getCampaigns(filters),
    staleTime: 30_000,
  });
}

export function useCampaign(id: string) {
  return useQuery({
    queryKey: ['campaigns', id],
    queryFn: () => getCampaign(id),
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useCreateCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CampaignCreateRequest) => createCampaign(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    },
  });
}

export function useUpdateCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: CampaignUpdateRequest }) =>
      updateCampaign(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    },
  });
}

export function useDeleteCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteCampaign(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    },
  });
}

export function useLinkCampaignObservable() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ campaignId, observableId }: { campaignId: string; observableId: string }) =>
      linkCampaignObservable(campaignId, observableId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    },
  });
}

export function useUnlinkCampaignObservable() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ campaignId, observableId }: { campaignId: string; observableId: string }) =>
      unlinkCampaignObservable(campaignId, observableId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    },
  });
}

export function useCampaignTimeline(campaignId: string) {
  return useQuery({
    queryKey: ['campaigns', campaignId, 'timeline'],
    queryFn: () => getCampaignTimeline(campaignId),
    enabled: !!campaignId,
    staleTime: 30_000,
  });
}

export function useCampaignsForObservable(observableId: string) {
  return useQuery({
    queryKey: ['observables', observableId, 'campaigns'],
    queryFn: () => getCampaignsForObservable(observableId),
    enabled: !!observableId,
    staleTime: 30_000,
  });
}
