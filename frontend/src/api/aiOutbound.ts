import api from './client'
import type { OutboundPreview, OutboundRef, AiProvider } from '@/types/ai'

const BASE = '/ai/outbound'

export interface OutboundPreviewRequest {
  provider: AiProvider
  model: string
  refs: OutboundRef[]
}

export async function postOutboundPreview(body: OutboundPreviewRequest): Promise<OutboundPreview> {
  const { data } = await api.post<OutboundPreview>(`${BASE}/preview`, body)
  return data
}
