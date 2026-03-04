import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getObservables, getObservable, createObservable, deleteObservable } from '@/api/observables'
import type { ObservableFilters, ObservableCreate } from '@/types/observable'

export function useObservables(params: ObservableFilters) {
  return useQuery({
    queryKey: ['observables', params],
    queryFn: () => getObservables(params),
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
    },
  })
}

export function useDeleteObservable() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteObservable(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observables'] })
    },
  })
}
