import client from './client';
import type {
  AlertRuleCreate,
  AlertRuleUpdate,
  AlertRuleResponse,
  AlertEventListResponse,
  WebhookConfigCreate,
  WebhookConfigUpdate,
  WebhookConfigResponse,
  WebhookTestResponse,
} from '@/types/alert';

// --- Alert Rules ---

export async function listAlertRules(): Promise<AlertRuleResponse[]> {
  const response = await client.get<AlertRuleResponse[]>('/alerts/rules');
  return response.data;
}

export async function createAlertRule(
  data: AlertRuleCreate
): Promise<AlertRuleResponse> {
  const response = await client.post<AlertRuleResponse>(
    '/alerts/rules',
    data
  );
  return response.data;
}

export async function updateAlertRule(
  id: string,
  data: AlertRuleUpdate
): Promise<AlertRuleResponse> {
  const response = await client.put<AlertRuleResponse>(
    `/alerts/rules/${id}`,
    data
  );
  return response.data;
}

export async function deleteAlertRule(id: string): Promise<void> {
  await client.delete(`/alerts/rules/${id}`);
}

// --- Alert Events ---

export async function listAlertEvents(params: {
  page?: number;
  size?: number;
  rule_id?: string;
}): Promise<AlertEventListResponse> {
  const response = await client.get<AlertEventListResponse>(
    '/alerts/events',
    { params }
  );
  return response.data;
}

// --- Webhooks ---

export async function listWebhooks(): Promise<WebhookConfigResponse[]> {
  const response = await client.get<WebhookConfigResponse[]>('/webhooks');
  return response.data;
}

export async function createWebhook(
  data: WebhookConfigCreate
): Promise<WebhookConfigResponse> {
  const response = await client.post<WebhookConfigResponse>(
    '/webhooks',
    data
  );
  return response.data;
}

export async function updateWebhook(
  id: string,
  data: WebhookConfigUpdate
): Promise<WebhookConfigResponse> {
  const response = await client.put<WebhookConfigResponse>(
    `/webhooks/${id}`,
    data
  );
  return response.data;
}

export async function deleteWebhook(id: string): Promise<void> {
  await client.delete(`/webhooks/${id}`);
}

export async function testWebhook(id: string): Promise<WebhookTestResponse> {
  const response = await client.post<WebhookTestResponse>(
    `/webhooks/${id}/test`
  );
  return response.data;
}
