import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getThreatActors,
  getThreatActor,
  createThreatActor,
  updateThreatActor,
  deleteThreatActor,
  linkThreatActorObservable,
  unlinkThreatActorObservable,
  linkThreatActorTechnique,
  unlinkThreatActorTechnique,
  getThreatActorCampaigns,
  getThreatActorsForObservable,
} from '@/api/threat_actors';
import type {
  ThreatActorFilters,
  ThreatActorCreateRequest,
  ThreatActorUpdateRequest,
} from '@/types/threat_actor';

export function useThreatActors(filters: ThreatActorFilters = {}) {
  return useQuery({
    queryKey: ['threat-actors', filters],
    queryFn: () => getThreatActors(filters),
    staleTime: 30_000,
  });
}

export function useThreatActor(id: string) {
  return useQuery({
    queryKey: ['threat-actors', id],
    queryFn: () => getThreatActor(id),
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useCreateThreatActor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ThreatActorCreateRequest) => createThreatActor(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['threat-actors'] });
    },
  });
}

export function useUpdateThreatActor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ThreatActorUpdateRequest }) =>
      updateThreatActor(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['threat-actors'] });
    },
  });
}

export function useDeleteThreatActor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteThreatActor(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['threat-actors'] });
    },
  });
}

export function useLinkThreatActorObservable() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ actorId, observableId }: { actorId: string; observableId: string }) =>
      linkThreatActorObservable(actorId, observableId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['threat-actors'] });
    },
  });
}

export function useUnlinkThreatActorObservable() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ actorId, observableId }: { actorId: string; observableId: string }) =>
      unlinkThreatActorObservable(actorId, observableId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['threat-actors'] });
    },
  });
}

export function useLinkThreatActorTechnique() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ actorId, techniqueId }: { actorId: string; techniqueId: string }) =>
      linkThreatActorTechnique(actorId, techniqueId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['threat-actors'] });
    },
  });
}

export function useUnlinkThreatActorTechnique() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ actorId, techniqueId }: { actorId: string; techniqueId: string }) =>
      unlinkThreatActorTechnique(actorId, techniqueId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['threat-actors'] });
    },
  });
}

export function useThreatActorCampaigns(actorId: string) {
  return useQuery({
    queryKey: ['threat-actors', actorId, 'campaigns'],
    queryFn: () => getThreatActorCampaigns(actorId),
    enabled: !!actorId,
    staleTime: 30_000,
  });
}

export function useThreatActorsForObservable(observableId: string) {
  return useQuery({
    queryKey: ['observables', observableId, 'threat-actors'],
    queryFn: () => getThreatActorsForObservable(observableId),
    enabled: !!observableId,
    staleTime: 30_000,
  });
}
