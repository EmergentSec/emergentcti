import api from './client'
import type { ExportProfile, ExportProfileInput, ExportProfilePreview } from '@/types/exportProfile'

export async function getExportProfiles(): Promise<ExportProfile[]> {
  const { data } = await api.get<ExportProfile[]>('/export/profiles')
  return data
}

export async function createExportProfile(payload: ExportProfileInput): Promise<ExportProfile> {
  const { data } = await api.post<ExportProfile>('/export/profiles', payload)
  return data
}

export async function updateExportProfile(id: string, payload: ExportProfileInput): Promise<ExportProfile> {
  const { data } = await api.put<ExportProfile>(`/export/profiles/${id}`, payload)
  return data
}

export async function deleteExportProfile(id: string): Promise<void> {
  await api.delete(`/export/profiles/${id}`)
}

export async function getExportProfilePreview(id: string): Promise<ExportProfilePreview> {
  const { data } = await api.get<ExportProfilePreview>(`/export/profiles/${id}/preview`)
  return data
}

/**
 * Relative download path for a saved profile — usable as an <a href download>
 * target (the browser sends the session cookie on navigation).
 */
export function exportProfileDownloadPath(id: string): string {
  return `/api/v1/export/profiles/${encodeURIComponent(id)}/download`
}

/**
 * Stable absolute download URL for firewalls and scripts. The URL carries no
 * credentials: clients authenticate with the X-API-Key header.
 */
export function exportProfileDownloadUrl(id: string, origin: string = window.location.origin): string {
  return `${origin.replace(/\/+$/, '')}${exportProfileDownloadPath(id)}`
}
