import api from './client'
import type {
  ReportAttachment,
  ReportCreate,
  ReportDetail,
  ReportFilters,
  ReportListResponse,
  ReportSummary,
  ReportUpdate,
  LinkedObservable,
} from '@/types/report'

function cleanParams(params: ReportFilters): Record<string, unknown> {
  const clean: Record<string, unknown> = {}
  for (const [key, val] of Object.entries(params)) {
    if (val !== undefined && val !== '' && val !== null) {
      clean[key] = val
    }
  }
  return clean
}

export async function getReports(params: ReportFilters = {}): Promise<ReportListResponse> {
  const { data } = await api.get<ReportListResponse>('/reports', { params: cleanParams(params) })
  return data
}

export async function getReportSources(): Promise<string[]> {
  const { data } = await api.get<string[]>('/reports/sources')
  return data
}

export async function getReport(id: string): Promise<ReportDetail> {
  const { data } = await api.get<ReportDetail>(`/reports/${id}`)
  return data
}

export async function createReport(payload: ReportCreate): Promise<ReportDetail> {
  const { data } = await api.post<ReportDetail>('/reports', payload)
  return data
}

export async function updateReport(id: string, payload: ReportUpdate): Promise<ReportDetail> {
  const { data } = await api.patch<ReportDetail>(`/reports/${id}`, payload)
  return data
}

export async function deleteReport(id: string): Promise<void> {
  await api.delete(`/reports/${id}`)
}

export async function uploadReportAttachment(id: string, file: File): Promise<ReportAttachment> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.put<ReportAttachment>(`/reports/${id}/attachment`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function removeReportAttachment(id: string): Promise<void> {
  await api.delete(`/reports/${id}/attachment`)
}

export async function downloadReportAttachment(id: string): Promise<Blob> {
  const { data } = await api.get<Blob>(`/reports/${id}/attachment`, { responseType: 'blob' })
  return data
}

export async function linkReportObservable(
  reportId: string,
  observableId: string,
): Promise<LinkedObservable> {
  const { data } = await api.post<LinkedObservable>(`/reports/${reportId}/observables`, {
    observable_id: observableId,
  })
  return data
}

export async function unlinkReportObservable(reportId: string, observableId: string): Promise<void> {
  await api.delete(`/reports/${reportId}/observables/${observableId}`)
}

export async function getObservableReports(observableId: string): Promise<ReportSummary[]> {
  const { data } = await api.get<ReportSummary[]>(`/observables/${observableId}/reports`)
  return data
}
