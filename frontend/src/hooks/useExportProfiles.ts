import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getExportProfiles,
  createExportProfile,
  updateExportProfile,
  deleteExportProfile,
  getExportProfilePreview,
} from '@/api/exportProfiles'
import type { ExportProfileInput } from '@/types/exportProfile'

export function useExportProfiles() {
  return useQuery({
    queryKey: ['exportProfiles'],
    queryFn: getExportProfiles,
  })
}

/** Preview is evaluated against current data and policy, so it is never served stale. */
export function useExportProfilePreview(id: string | null) {
  return useQuery({
    queryKey: ['exportProfilePreview', id],
    queryFn: () => getExportProfilePreview(id!),
    enabled: !!id,
    staleTime: 0,
    gcTime: 0,
  })
}

export function useCreateExportProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ExportProfileInput) => createExportProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exportProfiles'] })
    },
  })
}

export function useUpdateExportProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ExportProfileInput }) => updateExportProfile(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exportProfiles'] })
      queryClient.invalidateQueries({ queryKey: ['exportProfilePreview'] })
    },
  })
}

export function useDeleteExportProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteExportProfile(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exportProfiles'] })
    },
  })
}
