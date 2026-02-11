import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSavedSearches,
  createSavedSearch,
  updateSavedSearch,
  deleteSavedSearch,
  setDefaultSearch,
} from '@/api/saved_searches';
import type {
  SavedSearchCreate,
  SavedSearchUpdate,
} from '@/types/saved_search';

export function useSavedSearches() {
  return useQuery({
    queryKey: ['saved-searches'],
    queryFn: getSavedSearches,
    staleTime: 30_000,
  });
}

export function useCreateSavedSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SavedSearchCreate) => createSavedSearch(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-searches'] });
    },
  });
}

export function useUpdateSavedSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SavedSearchUpdate }) =>
      updateSavedSearch(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-searches'] });
    },
  });
}

export function useDeleteSavedSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteSavedSearch(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-searches'] });
    },
  });
}

export function useSetDefaultSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => setDefaultSearch(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-searches'] });
    },
  });
}
