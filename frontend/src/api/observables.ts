import api from './client'
import { buildListParams } from './listParams'
import type {
  Observable,
  ObservableListResponse,
  ObservableFilters,
  ObservableCreate,
  ObservableTagsUpdate,
  TlpOverrideRequest,
} from '@/types/observable'

export async function getObservables(params: ObservableFilters = {}): Promise<ObservableListResponse> {
  const { data } = await api.get<ObservableListResponse>('/observables', {
    params: buildListParams(params as Record<string, unknown>),
  })
  return data
}

export async function getObservable(id: string): Promise<Observable> {
  const { data } = await api.get<Observable>(`/observables/${id}`)
  return data
}

export async function createObservable(data: ObservableCreate): Promise<Observable> {
  const { data: result } = await api.post<Observable>('/observables', data)
  return result
}

export async function deleteObservable(id: string): Promise<void> {
  await api.delete(`/observables/${id}`)
}

export async function setConfidenceOverride(id: string, confidence: number): Promise<Observable> {
  const { data } = await api.put<Observable>(`/observables/${id}/confidence-override`, {
    confidence,
  })
  return data
}

export async function clearConfidenceOverride(id: string): Promise<Observable> {
  const { data } = await api.delete<Observable>(`/observables/${id}/confidence-override`)
  return data
}

export async function setTlpOverride(id: string, body: TlpOverrideRequest): Promise<Observable> {
  const { data } = await api.put<Observable>(`/observables/${id}/tlp-override`, body)
  return data
}

export async function clearTlpOverride(id: string): Promise<Observable> {
  const { data } = await api.delete<Observable>(`/observables/${id}/tlp-override`)
  return data
}

export async function setObservableTags(id: string, body: ObservableTagsUpdate): Promise<Observable> {
  const { data } = await api.put<Observable>(`/observables/${id}/tags`, body)
  return data
}
