import client from './client';
import type {
  TacticResponse,
  TechniqueResponse,
  HeatmapResponse,
  ObservableTechniqueResponse,
} from '@/types/attack';

export async function getTactics(): Promise<TacticResponse[]> {
  const response = await client.get<TacticResponse[]>('/attack/tactics');
  return response.data;
}

export async function getTechniques(
  tacticId?: string
): Promise<TechniqueResponse[]> {
  const params: Record<string, string> = {};
  if (tacticId) params.tactic_id = tacticId;

  const response = await client.get<TechniqueResponse[]>(
    '/attack/techniques',
    { params }
  );
  return response.data;
}

export async function getHeatmap(): Promise<HeatmapResponse> {
  const response = await client.get<HeatmapResponse>('/attack/heatmap');
  return response.data;
}

export async function syncAttackData(): Promise<void> {
  await client.post('/attack/sync');
}

export async function getObservableTechniques(
  observableId: string
): Promise<ObservableTechniqueResponse[]> {
  const response = await client.get<ObservableTechniqueResponse[]>(
    `/attack/observables/${observableId}/techniques`
  );
  return response.data;
}

export async function mapObservableTechnique(
  observableId: string,
  techniqueId: string
): Promise<ObservableTechniqueResponse> {
  const response = await client.post<ObservableTechniqueResponse>(
    `/attack/observables/${observableId}/techniques`,
    { technique_id: techniqueId }
  );
  return response.data;
}

export async function unmapObservableTechnique(
  observableId: string,
  techniqueId: string
): Promise<void> {
  await client.delete(
    `/attack/observables/${observableId}/techniques/${techniqueId}`
  );
}
