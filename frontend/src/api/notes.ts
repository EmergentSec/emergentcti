import client from './client';
import type { NoteResponse, NoteCreateRequest } from '@/types/observable';

export async function getNotes(observableId: string): Promise<NoteResponse[]> {
  const response = await client.get<NoteResponse[]>(`/observables/${observableId}/notes`);
  return response.data;
}

export async function createNote(observableId: string, data: NoteCreateRequest): Promise<NoteResponse> {
  const response = await client.post<NoteResponse>(`/observables/${observableId}/notes`, data);
  return response.data;
}

export async function deleteNote(observableId: string, noteId: string): Promise<void> {
  await client.delete(`/observables/${observableId}/notes/${noteId}`);
}
