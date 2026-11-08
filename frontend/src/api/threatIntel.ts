import api from './client'

export interface ThreatIntelSkill {
  id: string
  title: string
  path: string
}

export interface FeedFetchResponse {
  timestamp: string
  total_items: number
  summary: Record<string, unknown>
  items: Record<string, unknown>[]
  state_file: string
  config_path: string
}

export interface GenerateReportResponse {
  report_id: string
  title: string
  research_provider: string
  research_model: string
  writer_provider: string
  writer_model: string
  research_chars: number
  report_chars: number
}

const BASE = '/threat-intel'

export async function listThreatIntelSkills(): Promise<ThreatIntelSkill[]> {
  const { data } = await api.get<ThreatIntelSkill[]>(`${BASE}/skills`)
  return data
}

export async function fetchThreatIntelFeeds(): Promise<FeedFetchResponse> {
  const { data } = await api.post<FeedFetchResponse>(`${BASE}/fetch`)
  return data
}

export async function generateThreatIntelReport(
  item: Record<string, unknown>,
  environment: 'homelab' = 'homelab',
): Promise<GenerateReportResponse> {
  const { data } = await api.post<GenerateReportResponse>(`${BASE}/generate-report`, {
    item,
    environment,
  })
  return data
}