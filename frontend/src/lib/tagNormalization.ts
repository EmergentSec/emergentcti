/** Mirror backend tag normalization for inline UX hints (authority is the API). */
export function normalizeTagName(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) return ''
  return trimmed
    .split(/\s+/)
    .join('-')
    .toLowerCase()
}

const TAG_PATTERN = /^[a-z0-9._:/-]+$/

export function validateTagName(normalized: string): string | null {
  if (!normalized) return 'Tag name is required'
  if (normalized.length > 50) return 'Tag name must be 50 characters or fewer'
  if (!TAG_PATTERN.test(normalized)) {
    return 'Use lowercase letters, numbers, and . _ : / - only'
  }
  return null
}
