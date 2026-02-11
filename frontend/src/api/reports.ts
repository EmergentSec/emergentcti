import client from './client';
import type {
  ReportCreate,
  ReportResponse,
  ReportListResponse,
} from '@/types/report';

export async function createReport(
  data: ReportCreate
): Promise<ReportResponse> {
  const response = await client.post<ReportResponse>('/reports', data);
  return response.data;
}

export async function listReports(params: {
  page?: number;
  size?: number;
}): Promise<ReportListResponse> {
  const response = await client.get<ReportListResponse>('/reports', {
    params,
  });
  return response.data;
}

export async function getReport(id: string): Promise<ReportResponse> {
  const response = await client.get<ReportResponse>(`/reports/${id}`);
  return response.data;
}

export async function deleteReport(id: string): Promise<void> {
  await client.delete(`/reports/${id}`);
}

export function getReportDownloadUrl(id: string): string {
  return `/api/v1/reports/${id}/download`;
}
