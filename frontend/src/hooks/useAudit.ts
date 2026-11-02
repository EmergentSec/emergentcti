import { useQuery } from '@tanstack/react-query'
import { getAuditEvents, getAuditMeta, type AuditEventFilters } from '@/api/audit'

export function useAuditMeta() {
  return useQuery({
    queryKey: ['auditMeta'],
    queryFn: getAuditMeta,
  })
}

export function useAuditEvents(filters: AuditEventFilters) {
  return useQuery({
    queryKey: ['auditEvents', filters],
    queryFn: () => getAuditEvents(filters),
  })
}
