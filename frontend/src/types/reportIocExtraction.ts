export type CandidateStatus = 'new' | 'existing' | 'invalid'
export type SourceStatus = 'extracted' | 'empty' | 'unsupported'

export type ExtractionCandidateType =
  | 'ip-addr'
  | 'domain-name'
  | 'url'
  | 'file-hash'
  | 'email-addr'

export interface ExtractionSource {
  kind: 'content' | 'attachment'
  filename: string | null
  content_type: string | null
  status: SourceStatus
  reason: string | null
}

export interface ExtractionCandidate {
  type: ExtractionCandidateType
  value: string
  original: string
  context: string
  occurrences: number
  defanged: boolean
  status: CandidateStatus
  existing_observable_id: string | null
  existing_confidence: number | null
  already_attributed: boolean
  allowlisted: boolean
  allowlist_matches: string[]
  warnings: string[]
}

export interface ExtractionPreview {
  report_id: string
  sources: ExtractionSource[]
  candidates: ExtractionCandidate[]
  truncated: boolean
  counts: { total: number; new: number; existing: number; invalid: number }
}

export interface ImportRequest {
  confidence: number
  items: { type: string; value: string }[]
}

export interface ImportResult {
  created: number
  attributed_existing: number
  already_attributed: number
  observables: {
    id: string
    type: string
    value: string
    confidence_score: number
    created: boolean
  }[]
}
