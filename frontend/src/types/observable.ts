export type ObservableType =
  | 'ip-addr'
  | 'domain-name'
  | 'url'
  | 'file-hash'
  | 'email-addr'
  | 'command-line'
  | 'user-agent'
  | 'certificate'
  | 'asn'
  | 'cidr';

export type TLPLevel = 'clear' | 'green' | 'amber' | 'amber+strict' | 'red';

export const OBSERVABLE_CATEGORIES = [
  'malware', 'c2', 'trojan', 'phishing', 'ransomware', 'botnet',
  'exploit', 'apt', 'scanner', 'spam', 'suspicious', 'benign', 'other',
] as const;

export type ObservableCategory = typeof OBSERVABLE_CATEGORIES[number];

export interface FeedSource {
  id: string;
  name: string;
}

export interface ObservableResponse {
  id: string;
  type: ObservableType;
  value: string;
  tlp: TLPLevel;
  confidence_score: number;
  tags: string[];
  context: Record<string, unknown> | null;
  category: string | null;
  description: string | null;
  external_references: Array<{source: string; url: string; description: string}> | null;
  sources: FeedSource[];
  first_seen: string | null;
  last_seen: string | null;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ObservableCreateRequest {
  type: ObservableType;
  value: string;
  tlp?: TLPLevel;
  confidence_score?: number;
  tags?: string[];
  context?: Record<string, unknown>;
  category?: string | null;
  description?: string;
}

export interface ObservableUpdateRequest {
  tlp?: TLPLevel;
  confidence_score?: number;
  tags?: string[];
  context?: Record<string, unknown>;
  category?: string | null;
  description?: string;
}

export interface ObservableFilters {
  page?: number;
  size?: number;
  type?: ObservableType | '';
  value?: string;
  confidence_min?: number;
  tlp?: TLPLevel | '';
  feed_id?: string;
  is_active?: string;
}

export interface ObservableStats {
  total: number;
  by_type: Record<string, number>;
}

export interface NoteAuthor {
  id: string;
  username: string;
}

export interface NoteResponse {
  id: string;
  observable_id: string;
  content: string;
  author: NoteAuthor;
  created_at: string;
  updated_at: string;
}

export interface NoteCreateRequest {
  content: string;
}
