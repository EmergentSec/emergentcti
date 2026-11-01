/** Client-side auth_config validation (mirrors backend rules; no secrets in messages). */

export function validateFullAuthConfig(
  obj: unknown,
  feedUrl?: string | null,
): string | null {
  if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) {
    return 'Auth config must be a JSON object'
  }

  const record = obj as Record<string, unknown>
  const authType = record.auth_type

  if (typeof authType !== 'string' || !authType.trim()) {
    return 'auth_type is required (api_key, bearer, or url_template)'
  }

  switch (authType) {
    case 'api_key': {
      const header = record.api_key_header
      const value = record.api_key_value
      if (typeof header !== 'string' || !header.trim()) {
        return 'api_key_header is required for api_key auth'
      }
      if (typeof value !== 'string' || !value.trim()) {
        return 'api_key_value is required for api_key auth'
      }
      break
    }
    case 'bearer': {
      const token = record.token ?? record.api_key_value
      if (typeof token !== 'string' || !token.trim()) {
        return 'token (or api_key_value) is required for bearer auth'
      }
      break
    }
    case 'url_template': {
      const value = record.api_key_value
      if (typeof value !== 'string' || !value.trim()) {
        return 'api_key_value is required for url_template auth'
      }
      const url = (feedUrl ?? '').trim()
      if (!url.includes('{api_key}')) {
        return 'Feed URL must contain {api_key} for url_template auth'
      }
      break
    }
    default:
      return `Unknown auth_type "${authType}"`
  }

  return null
}

export const AUTH_CONFIG_EXAMPLES = `Examples:
• api_key: {"auth_type":"api_key","api_key_header":"X-API-Key","api_key_value":"…"}
• bearer: {"auth_type":"bearer","token":"…"}
• url_template: {"auth_type":"url_template","api_key_value":"…"} (URL must include {api_key})`

export const AUTH_CONFIG_PLACEHOLDER = '{"auth_type":"api_key","api_key_header":"X-API-Key","api_key_value":"…"}'
