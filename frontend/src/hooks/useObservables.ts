import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getObservables,
  getObservable,
  createObservable,
  deleteObservable,
  setConfidenceOverride,
  clearConfidenceOverride,
} from '@/api/observables'
import type { ObservableFilters, ObservableCreate } from '@/types/observable'

export function useObservables(params: ObservableFilters, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['observables', params],
    queryFn: () => getObservables(params),
    enabled: options?.enabled ?? true,
  })
}

export function useObservable(id: string | null) {
  return useQuery({
    queryKey: ['observable', id],
    queryFn: () => getObservable(id!),
    enabled: !!id,
  })
}

export function useCreateObservable() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ObservableCreate) => createObservable(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observables'] })
      // Dashboard KPIs and the sidebar observable badge read this query.
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useDeleteObservable() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteObservable(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observables'] })
      // Dashboard KPIs and the sidebar observable badge read this query.
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

function invalidateObservableViews(queryClient: ReturnType<typeof useQueryClient>, id: string) {
  queryClient.invalidateQueries({ queryKey: ['observable', id] })
  queryClient.invalidateQueries({ queryKey: ['observables'] })
  queryClient.invalidateQueries({ queryKey: ['dashboard'] })
}

export function useSetConfidenceOverride() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, confidence }: { id: string; confidence: number }) =>
      setConfidenceOverride(id, confidence),
    onSuccess: (_data, { id }) => invalidateObservableViews(queryClient, id),
  })
}

export function useClearConfidenceOverride() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => clearConfidenceOverride(id),
    onSuccess: (_data, id) => invalidateObservableViews(queryClient, id),
  })
}
