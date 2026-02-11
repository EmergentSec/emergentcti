export interface ReportCreate {
  title: string;
  report_type: 'threat_summary' | 'observable_report' | 'campaign_brief';
  parameters: Record<string, unknown>;
  format: 'pdf' | 'html';
}

export interface ReportResponse {
  id: string;
  title: string;
  report_type: string;
  parameters: Record<string, unknown>;
  status: 'pending' | 'generating' | 'ready' | 'failed';
  format: string;
  file_path: string | null;
  generated_by: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ReportListResponse {
  items: ReportResponse[];
  total: number;
}
