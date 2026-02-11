import client from './client';
import type {
  RelationshipResponse,
  RelationshipCreate,
  RelationshipUpdate,
  GraphResponse,
} from '@/types/relationship';

export async function getRelationships(
  observableId: string,
  direction?: string
): Promise<RelationshipResponse[]> {
  const params: Record<string, string> = {};
  if (direction) params.direction = direction;

  const { data } = await client.get<RelationshipResponse[]>(
    `/observables/${observableId}/relationships`,
    { params }
  );
  return data;
}

export async function createRelationship(
  observableId: string,
  body: RelationshipCreate
): Promise<RelationshipResponse> {
  const { data } = await client.post<RelationshipResponse>(
    `/observables/${observableId}/relationships`,
    body
  );
  return data;
}

export async function getObservableGraph(
  observableId: string,
  depth?: number
): Promise<GraphResponse> {
  const params: Record<string, number> = {};
  if (depth !== undefined) params.depth = depth;

  const { data } = await client.get<GraphResponse>(
    `/observables/${observableId}/graph`,
    { params }
  );
  return data;
}

export async function updateRelationship(
  id: string,
  body: RelationshipUpdate
): Promise<RelationshipResponse> {
  const { data } = await client.put<RelationshipResponse>(
    `/relationships/${id}`,
    body
  );
  return data;
}

export async function deleteRelationship(id: string): Promise<void> {
  await client.delete(`/relationships/${id}`);
}
