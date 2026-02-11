export interface ExportParams {
  type?: string;
  value?: string;
  confidence_min?: number;
  tlp?: string;
  category?: string;
  tag?: string;
  feed_id?: string;
  skip?: number;
  limit?: number;
}

export interface CSVPreviewResponse {
  detected_mapping: Record<string, string>;
  rows: Record<string, string>[];
  total_rows: number;
  errors: string[];
}

export interface CSVImportResponse {
  imported: number;
  skipped: number;
  errors: string[];
}

export interface STIXImportResponse {
  imported: number;
  skipped: number;
  errors: string[];
}
