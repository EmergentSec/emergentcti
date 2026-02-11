import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getRelationships,
  createRelationship,
  getObservableGraph,
  updateRelationship,
  deleteRelationship,
} from '@/api/relationships';
import type {
  RelationshipCreate,
  RelationshipUpdate,
} from '@/types/relationship';

export function useRelationships(observableId: string) {
  return useQuery({
    queryKey: ['observables', observableId, 'relationships'],
    queryFn: () => getRelationships(observableId),
    enabled: !!observableId,
    staleTime: 30_000,
  });
}

export function useObservableGraph(observableId: string, depth?: number) {
  return useQuery({
    queryKey: ['observables', observableId, 'graph', depth],
    queryFn: () => getObservableGraph(observableId, depth),
    enabled: !!observableId,
    staleTime: 30_000,
  });
}

export function useCreateRelationship() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      observableId,
      data,
    }: {
      observableId: string;
      data: RelationshipCreate;
    }) => createRelationship(observableId, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['observables', variables.observableId, 'relationships'],
      });
      queryClient.invalidateQueries({
        queryKey: ['observables', variables.observableId, 'graph'],
      });
    },
  });
}

export function useUpdateRelationship() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: RelationshipUpdate;
    }) => updateRelationship(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observables'] });
    },
  });
}

export function useDeleteRelationship() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteRelationship(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observables'] });
    },
  });
}
