import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getObservables,
  getObservable,
  createObservable,
  updateObservable,
  deleteObservable,
  getObservableStats,
  bulkUpdateObservables,
  bulkDeleteObservables,
} from '@/api/observables';
import { getNotes, createNote, deleteNote } from '@/api/notes';
import type {
  ObservableFilters,
  ObservableCreateRequest,
  ObservableUpdateRequest,
  NoteCreateRequest,
} from '@/types/observable';

export function useObservables(filters: ObservableFilters = {}) {
  return useQuery({
    queryKey: ['observables', filters],
    queryFn: () => getObservables(filters),
    staleTime: 30_000,
  });
}

export function useObservable(id: string) {
  return useQuery({
    queryKey: ['observables', id],
    queryFn: () => getObservable(id),
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useObservableStats() {
  return useQuery({
    queryKey: ['observables', 'stats'],
    queryFn: getObservableStats,
    staleTime: 30_000,
  });
}

export function useCreateObservable() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ObservableCreateRequest) => createObservable(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observables'] });
    },
  });
}

export function useUpdateObservable() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: ObservableUpdateRequest;
    }) => updateObservable(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observables'] });
    },
  });
}

export function useDeleteObservable() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteObservable(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observables'] });
    },
  });
}

export function useObservableNotes(observableId: string) {
  return useQuery({
    queryKey: ['observables', observableId, 'notes'],
    queryFn: () => getNotes(observableId),
    enabled: !!observableId,
    staleTime: 30_000,
  });
}

export function useCreateNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ observableId, data }: { observableId: string; data: NoteCreateRequest }) =>
      createNote(observableId, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['observables', variables.observableId, 'notes'] });
    },
  });
}

export function useDeleteNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ observableId, noteId }: { observableId: string; noteId: string }) =>
      deleteNote(observableId, noteId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['observables', variables.observableId, 'notes'] });
    },
  });
}

export function useBulkUpdateObservables() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      ids,
      updates,
    }: {
      ids: string[];
      updates: {
        tlp?: string;
        confidence_score?: number;
        tags?: string[];
        add_tags?: string[];
        category?: string;
      };
    }) => bulkUpdateObservables(ids, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observables'] });
    },
  });
}

export function useBulkDeleteObservables() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => bulkDeleteObservables(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observables'] });
    },
  });
}
