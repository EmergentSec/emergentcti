/**
 * Build query params for list endpoints. Repeatable keys (`tag`, `tlp`) are
 * emitted as repeated query parameters (`tag=a&tag=b`), matching FastAPI.
 */
export function buildListParams(
  params: Record<string, unknown>,
): Record<string, unknown> | URLSearchParams {
  const flat: Record<string, unknown> = {}
  const repeated: [string, string][] = []

  for (const [key, val] of Object.entries(params)) {
    if (val === undefined || val === '' || val === null) continue
    if (key === 'tag' || key === 'tlp') {
      const arr = Array.isArray(val) ? val : [val]
      for (const item of arr) {
        if (item !== undefined && item !== '' && item !== null) {
          repeated.push([key, String(item)])
        }
      }
      continue
    }
    flat[key] = val
  }

  if (repeated.length === 0) return flat

  const search = new URLSearchParams()
  for (const [key, val] of Object.entries(flat)) {
    search.append(key, String(val))
  }
  for (const [key, val] of repeated) {
    search.append(key, val)
  }
  return search
}
