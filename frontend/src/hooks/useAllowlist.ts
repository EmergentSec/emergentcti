import { useQuery, useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { getAllowlist, createAllowlistEntry, deleteAllowlistEntry } from '@/api/allowlist'
import type { AllowlistEntryCreate } from '@/types/allowlist'

// Allowlist matching is evaluated at read time, so a policy change alters the
// allowlisted flag on observables and the result of every profile preview.
function invalidatePolicyDependents(queryClient: QueryClient) {
  queryClient.invalidateQueries({ queryKey: ['allowlist'] })
  queryClient.invalidateQueries({ queryKey: ['observables'] })
  queryClient.invalidateQueries({ queryKey: ['observable'] })
  queryClient.invalidateQueries({ queryKey: ['exportProfilePreview'] })
}

export function useAllowlist() {
  return useQuery({
    queryKey: ['allowlist'],
    queryFn: getAllowlist,
  })
}

export function useCreateAllowlistEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: AllowlistEntryCreate) => createAllowlistEntry(data),
    onSuccess: () => invalidatePolicyDependents(queryClient),
  })
}

export function useDeleteAllowlistEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteAllowlistEntry(id),
    onSuccess: () => invalidatePolicyDependents(queryClient),
  })
}
