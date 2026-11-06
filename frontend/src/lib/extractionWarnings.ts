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

const PDF_REASON_LABELS: Record<string, string> = {
  pdf_no_text_layer: 'No text layer (scanned or image-only PDF)',
  pdf_encrypted: 'Encrypted PDF',
  pdf_malformed: 'Malformed or damaged PDF',
  pdf_too_large: 'PDF too large to extract',
  pdf_too_many_pages: 'PDF has too many pages to extract',
  pdf_too_complex: 'PDF too complex to extract',
  pdf_extraction_timeout: 'PDF extraction timed out',
  pdf_extraction_failed: 'PDF extraction failed',
}

const PASTE_HINT = 'Paste the report text into the report content to extract indicators.'

export const PDF_NO_TEXT_LAYER_MESSAGE = `This PDF has little or no extractable text; it looks scanned or image-only, and OCR is not supported. ${PASTE_HINT}`

export const PDF_UNREADABLE_MESSAGE = `Text could not be read from this PDF. ${PASTE_HINT}`

export function formatSourceReason(reason: string): string {
  return PDF_REASON_LABELS[reason] ?? reason.replace(/_/g, ' ')
}

/** Notice for an unsupported PDF source, or null when none applies. */
export function pdfSourceNotice(source: { status: string; reason: string | null }): string | null {
  if (source.status !== 'unsupported' || !source.reason?.startsWith('pdf_')) return null
  return source.reason === 'pdf_no_text_layer' ? PDF_NO_TEXT_LAYER_MESSAGE : PDF_UNREADABLE_MESSAGE
}

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
