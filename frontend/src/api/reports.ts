import api from './client'
import { buildListParams } from './listParams'
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
import type { ExtractionPreview, ImportRequest, ImportResult } from '@/types/reportIocExtraction'

function cleanParams(params: ReportFilters): Record<string, unknown> | URLSearchParams {
  return buildListParams(params as Record<string, unknown>)
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

/**
 * The backend's report create/patch schemas have no `tags` field (unknown keys
 * are ignored), so tags are saved with the dedicated admin-only
 * `PUT /reports/{id}/tags` call after the report itself is written.
 */
export async function createReport(payload: ReportCreate): Promise<ReportDetail> {
  const { tags, ...body } = payload
  const { data } = await api.post<ReportDetail>('/reports', body)
  if (tags && tags.length > 0) return setReportTags(data.id, tags)
  return data
}

export async function updateReport(id: string, payload: ReportUpdate): Promise<ReportDetail> {
  const { tags, ...body } = payload
  const { data } = await api.patch<ReportDetail>(`/reports/${id}`, body)
  if (tags !== undefined) return setReportTags(id, tags)
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

export async function extractReportIndicators(reportId: string): Promise<ExtractionPreview> {
  const { data } = await api.post<ExtractionPreview>(`/reports/${reportId}/extract`)
  return data
}

export async function importReportIndicators(
  reportId: string,
  payload: ImportRequest,
): Promise<ImportResult> {
  const { data } = await api.post<ImportResult>(`/reports/${reportId}/import`, payload)
  return data
}

export async function setReportTags(reportId: string, tags: string[]): Promise<ReportDetail> {
  const { data } = await api.put<ReportDetail>(`/reports/${reportId}/tags`, { tags })
  return data
}
