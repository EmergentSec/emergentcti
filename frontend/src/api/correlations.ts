import client from './client';
import type {
  CorrelationRuleCreate,
  CorrelationRuleUpdate,
  CorrelationRuleResponse,
  CorrelationEventListResponse,
} from '@/types/correlation';

// --- Correlation Rules ---

export async function listCorrelationRules(): Promise<CorrelationRuleResponse[]> {
  const response = await client.get<CorrelationRuleResponse[]>('/correlations/rules');
  return response.data;
}

export async function createCorrelationRule(
  data: CorrelationRuleCreate
): Promise<CorrelationRuleResponse> {
  const response = await client.post<CorrelationRuleResponse>(
    '/correlations/rules',
    data
  );
  return response.data;
}

export async function updateCorrelationRule(
  id: string,
  data: CorrelationRuleUpdate
): Promise<CorrelationRuleResponse> {
  const response = await client.put<CorrelationRuleResponse>(
    `/correlations/rules/${id}`,
    data
  );
  return response.data;
}

export async function deleteCorrelationRule(id: string): Promise<void> {
  await client.delete(`/correlations/rules/${id}`);
}

// --- Correlation Events ---

export async function listCorrelationEvents(params: {
  page?: number;
  size?: number;
}): Promise<CorrelationEventListResponse> {
  const response = await client.get<CorrelationEventListResponse>(
    '/correlations/events',
    { params }
  );
  return response.data;
}

// --- Trigger ---

export async function triggerCorrelationRun(): Promise<{ correlated: number }> {
  const response = await client.post<{ correlated: number }>(
    '/correlations/run'
  );
  return response.data;
}
