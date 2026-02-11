import client from './client';
import type { AuditLogListResponse, AuditLogResponse } from '@/types/audit';

export interface AuditLogParams {
  page?: number;
  size?: number;
  user_id?: string;
  entity_type?: string;
  entity_id?: string;
  action?: string;
}

export async function listAuditLogs(
  params: AuditLogParams
): Promise<AuditLogListResponse> {
  const response = await client.get<AuditLogListResponse>('/audit', {
    params,
  });
  return response.data;
}

export async function getEntityAuditLogs(
  entityType: string,
  entityId: string,
  limit: number = 50
): Promise<AuditLogResponse[]> {
  const response = await client.get<AuditLogResponse[]>(
    `/audit/entity/${entityType}/${entityId}`,
    { params: { limit } }
  );
  return response.data;
}
