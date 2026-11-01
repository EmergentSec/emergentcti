import type { CandidateStatus } from '@/types/reportIocExtraction'

const WARNING_LABELS: Record<string, string> = {
  invalid_ip: 'Invalid IP address',
  invalid_hash: 'Invalid hash',
  invalid_domain: 'Invalid domain',
  invalid_url: 'Invalid URL',
  invalid_email: 'Invalid email address',
  non_public_ip: 'Non-public IP address',
  looks_like_filename: 'Looks like a filename',
  hash_md5: 'MD5 hash (weaker algorithm)',
  hash_sha1: 'SHA-1 hash (weaker algorithm)',
}

export function formatExtractionWarning(code: string): string {
  return WARNING_LABELS[code] ?? code.replace(/_/g, ' ')
}

export const PDF_EXTRACTION_MESSAGE =
  'PDF text extraction is not available yet; paste the report text into the report content to extract indicators.'

export const CONFIDENCE_HELP_TEXT =
  'Applies to newly created observables only. Existing observables keep their current confidence and sources. This is your judgment, not a score derived from the report.'

export const EXPORT_ELIGIBILITY_NOTICE =
  'Imported indicators can appear in blocklist exports and export profiles under current policies (for example, the default blocklist threshold of 70). Allowlisted values stay excluded from exports.'

export function candidateKey(type: string, value: string): string {
  return `${type}\0${value}`
}

export function isSelectableCandidate(candidate: { status: CandidateStatus }): boolean {
  return candidate.status !== 'invalid'
}

export function isDefaultSelectedCandidate(candidate: {
  status: CandidateStatus
  already_attributed: boolean
  allowlisted: boolean
}): boolean {
  if (candidate.status === 'invalid') return false
  if (candidate.already_attributed) return false
  if (candidate.allowlisted) return false
  return candidate.status === 'new' || candidate.status === 'existing'
}
