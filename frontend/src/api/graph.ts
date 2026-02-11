import client from './client';
import type { GraphData } from '@/types/graph';

export interface GraphFilters {
  includeThreatActors?: boolean;
  includeCampaigns?: boolean;
  includeTechniques?: boolean;
}

export async function fetchGraph(
  entityType: string,
  entityId: string,
  depth: number = 2,
  filters?: GraphFilters
): Promise<GraphData> {
  const params: Record<string, string> = {};
  params.depth = String(depth);
  if (filters?.includeThreatActors === false)
    params.include_threat_actors = 'false';
  if (filters?.includeCampaigns === false)
    params.include_campaigns = 'false';
  if (filters?.includeTechniques === false)
    params.include_techniques = 'false';

  const response = await client.get<GraphData>(
    `/graph/${entityType}/${entityId}`,
    { params }
  );
  return response.data;
}
