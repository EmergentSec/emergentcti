import type { ObservableType } from './observable'

export type AllowlistKind = 'exact' | 'cidr' | 'domain_suffix'

export interface AllowlistEntry {
  id: string
  kind: AllowlistKind
  value: string
  observable_type: ObservableType
  reason: string
  created_at: string
  updated_at: string
}

export interface AllowlistEntryCreate {
  kind: AllowlistKind
  value: string
  observable_type?: ObservableType
  reason: string
}
