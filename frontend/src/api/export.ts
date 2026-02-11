import client from './client';
import type {
  ExportParams,
  CSVPreviewResponse,
  CSVImportResponse,
  STIXImportResponse,
} from '@/types/export';

function triggerDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function exportSTIX(params: ExportParams): Promise<void> {
  const response = await client.get('/export/stix', {
    params,
    responseType: 'blob',
  });
  triggerDownload(response.data as Blob, 'observables.stix.json');
}

export async function exportCSV(params: ExportParams): Promise<void> {
  const response = await client.get('/export/csv', {
    params,
    responseType: 'blob',
  });
  triggerDownload(response.data as Blob, 'observables.csv');
}

export async function exportJSON(params: ExportParams): Promise<void> {
  const response = await client.get('/export/json', {
    params,
    responseType: 'blob',
  });
  triggerDownload(response.data as Blob, 'observables.json');
}

export async function previewCSVImport(
  file: File,
  columnMapping?: Record<string, string>
): Promise<CSVPreviewResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (columnMapping) {
    formData.append('column_mapping', JSON.stringify(columnMapping));
  }
  const response = await client.post<CSVPreviewResponse>(
    '/import/csv/preview',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return response.data;
}

export async function importCSV(
  file: File,
  columnMapping: Record<string, string>
): Promise<CSVImportResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('column_mapping', JSON.stringify(columnMapping));
  const response = await client.post<CSVImportResponse>(
    '/import/csv',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return response.data;
}

export async function importSTIX(file: File): Promise<STIXImportResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await client.post<STIXImportResponse>(
    '/import/stix',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return response.data;
}

export async function exportSelected(
  ids: string[],
  format: 'stix' | 'csv' | 'json'
): Promise<void> {
  const response = await client.post(
    '/export/selected',
    { ids, format },
    { responseType: 'blob' }
  );

  const extensions: Record<string, string> = {
    stix: 'stix.json',
    csv: 'csv',
    json: 'json',
  };

  triggerDownload(response.data as Blob, `export.${extensions[format] || 'json'}`);
}
