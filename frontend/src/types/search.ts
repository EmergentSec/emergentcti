import type { ObservableType } from './observable';

export interface SearchParams {
  q: string;
  type?: ObservableType | '';
  page?: number;
  size?: number;
}

export interface SearchHit {
  id: string;
  type: ObservableType;
  value: string;
  confidence: number;
  tlp: string;
  source: string;
  tags: string[];
  first_seen: string;
  last_seen: string;
  score: number;
}

export interface SearchResponse {
  hits: SearchHit[];
  total: number;
  page: number;
  size: number;
}
