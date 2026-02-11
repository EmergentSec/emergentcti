import { useQuery } from '@tanstack/react-query';
import { listAuditLogs, getEntityAuditLogs } from '@/api/audit';
import type { AuditLogParams } from '@/api/audit';

export function useAuditLogs(params: AuditLogParams) {
  return useQuery({
    queryKey: ['auditLogs', params],
    queryFn: () => listAuditLogs(params),
    staleTime: 15_000,
  });
}

export function useEntityAuditLogs(
  entityType: string,
  entityId: string,
  limit: number = 50
) {
  return useQuery({
    queryKey: ['auditLogs', 'entity', entityType, entityId, limit],
    queryFn: () => getEntityAuditLogs(entityType, entityId, limit),
    staleTime: 15_000,
    enabled: !!entityType && !!entityId,
  });
}
