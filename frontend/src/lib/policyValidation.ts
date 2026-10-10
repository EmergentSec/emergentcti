import type { AllowlistKind } from '@/types/allowlist'
import type { ObservableType } from '@/types/observable'

// Mirrors the backend limits; the API remains the authority on canonical form
// and duplicates.
export const REASON_MAX_LENGTH = 500
export const ALLOWLIST_VALUE_MAX_BYTES = 2048
export const PROFILE_NAME_MAX_LENGTH = 100
export const PROFILE_DESCRIPTION_MAX_LENGTH = 500
export const MAX_EXPORT_AGE_DAYS = 36500

export interface AllowlistFormValues {
  kind: AllowlistKind
  value: string
  observableType: ObservableType | ''
  reason: string
}

export type AllowlistFormErrors = Partial<Record<'value' | 'observableType' | 'reason', string>>

function isIpv4(addr: string): boolean {
  const parts = addr.split('.')
  return parts.length === 4 && parts.every((p) => /^\d{1,3}$/.test(p) && Number(p) <= 255)
}

function isIpv6(addr: string): boolean {
  return addr.includes(':') && /^[0-9a-f:.]+$/i.test(addr)
}

function cidrError(value: string): string | undefined {
  const parts = value.split('/')
  if (parts.length !== 2 || !/^\d{1,3}$/.test(parts[1])) {
    return 'Enter a CIDR range such as 10.0.0.0/8 or 2001:db8::/32'
  }
  const prefix = Number(parts[1])
  if (isIpv4(parts[0])) return prefix <= 32 ? undefined : 'IPv4 prefix length must be between 0 and 32'
  if (isIpv6(parts[0])) return prefix <= 128 ? undefined : 'IPv6 prefix length must be between 0 and 128'
  return 'Enter a CIDR range such as 10.0.0.0/8 or 2001:db8::/32'
}

function domainSuffixError(value: string): string | undefined {
  const host = value.replace(/\.$/, '')
  if (/[\s/:@*?#\\]/.test(host) || host.startsWith('.') || host.split('.').some((label) => label === '')) {
    return 'Enter a bare domain such as example.com — subdomains are matched automatically'
  }
  return undefined
}

export function validateAllowlistEntry(values: AllowlistFormValues): AllowlistFormErrors {
  const errors: AllowlistFormErrors = {}
  const value = values.value.trim()
  const reason = values.reason.trim()

  if (!value) {
    errors.value = 'Value is required'
  } else if (values.kind === 'cidr') {
    const err = cidrError(value)
    if (err) errors.value = err
  } else if (values.kind === 'domain_suffix' || (values.kind === 'exact' && values.observableType === 'domain-name')) {
    const err = domainSuffixError(value)
    if (err) errors.value = err
  }

  const literal = values.kind === 'exact' && values.observableType !== 'ip-addr'
    && values.observableType !== 'domain-name'
  if (new TextEncoder().encode(literal ? values.value : value).length > ALLOWLIST_VALUE_MAX_BYTES) {
    errors.value = `Value must be ${ALLOWLIST_VALUE_MAX_BYTES} UTF-8 bytes or fewer`
  }

  if (values.kind === 'exact' && !values.observableType) {
    errors.observableType = 'Choose the observable type this value applies to'
  }

  if (!reason) {
    errors.reason = 'Reason is required'
  } else if (reason.length > REASON_MAX_LENGTH) {
    errors.reason = `Reason must be ${REASON_MAX_LENGTH} characters or fewer`
  }

  return errors
}

export interface ProfileFormValues {
  name: string
  description: string
  confidenceMin: string
  maxAgeDays: string
}

export type ProfileFormErrors = Partial<Record<keyof ProfileFormValues, string>>

export function validateExportProfile(values: ProfileFormValues): ProfileFormErrors {
  const errors: ProfileFormErrors = {}
  const name = values.name.trim()

  if (!name) {
    errors.name = 'Name is required'
  } else if (name.length > PROFILE_NAME_MAX_LENGTH) {
    errors.name = `Name must be ${PROFILE_NAME_MAX_LENGTH} characters or fewer`
  }

  if (values.description.trim().length > PROFILE_DESCRIPTION_MAX_LENGTH) {
    errors.description = `Description must be ${PROFILE_DESCRIPTION_MAX_LENGTH} characters or fewer`
  }

  const confidence = values.confidenceMin.trim()
  if (!/^\d+$/.test(confidence) || Number(confidence) > 100) {
    errors.confidenceMin = 'Minimum confidence must be a whole number from 0 to 100'
  }

  const maxAge = values.maxAgeDays.trim()
  if (maxAge && (!/^\d+$/.test(maxAge) || Number(maxAge) < 1 || Number(maxAge) > MAX_EXPORT_AGE_DAYS)) {
    errors.maxAgeDays = `Maximum age must be a whole number from 1 to ${MAX_EXPORT_AGE_DAYS} days (leave blank for any age)`
  }

  return errors
}
