/**
 * Validate in-app paths before React Router Link / navigate (GHSA-wrjc-x8rr-h8h6 class).
 */
export function isSafeAppPath(path: string): boolean {
  return (
    path.startsWith('/') &&
    !path.startsWith('//') &&
    !path.startsWith('/\\') &&
    !path.includes('\\')
  )
}

/** Return path or null when unsafe (open-redirect / protocol-relative patterns). */
export function safeAppPath(path: string): string | null {
  return isSafeAppPath(path) ? path : null
}

/** Build `/base/id` for entity deep links; rejects path metacharacters in id segments. */
export function entityDetailPath(base: string, entityId: string): string | null {
  const id = entityId.trim()
  if (!id || /[\\/?#]/.test(id)) return null
  const normalizedBase = base.replace(/\/+$/, '')
  return safeAppPath(`${normalizedBase}/${id}`)
}

/** Feeds page highlight query; id is query value only, path stays fixed. */
export function feedsHighlightPath(feedId: string): string | null {
  const id = feedId.trim()
  if (!id || /[\\/?#&=]/.test(id)) return null
  return safeAppPath(`/feeds?feed=${encodeURIComponent(id)}`)
}
