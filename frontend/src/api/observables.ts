import api from './client'
import type { Observable, ObservableListResponse, ObservableFilters, ObservableCreate } from '@/types/observable'

export async function getObservables(params: ObservableFilters = {}): Promise<ObservableListResponse> {
  // Strip empty/undefined params before sending
  const cleanParams: Record<string, unknown> = {}
  for (const [key, val] of Object.entries(params)) {
    if (val !== undefined && val !== '' && val !== null) {
      cleanParams[key] = val
    }
  }
  const { data } = await api.get<ObservableListResponse>('/observables', { params: cleanParams })
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
