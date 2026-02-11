export interface AuditLogResponse {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  user_id: string | null;
  username: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogResponse[];
  total: number;
  page: number;
  size: number;
  pages: number;
}
