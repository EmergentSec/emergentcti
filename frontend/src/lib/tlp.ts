import type { ExcludedByTlpCounts, ExportDestination, Tlp } from '@/types/tlp'

export const TLP_VALUES: Tlp[] = ['clear', 'green', 'amber', 'amber+strict', 'red']

export const TLP_RANK: Record<Tlp, number> = {
  clear: 0,
  green: 1,
  amber: 2,
  'amber+strict': 3,
  red: 4,
}

/** One-line meanings from the #15 contract (tooltip copy). */
export const TLP_MEANINGS: Record<Tlp, string> = {
  clear: 'Disclosure is not limited.',
  green: 'Share within your community, not publicly.',
  amber: 'Share within your organization and its clients on a need-to-know basis.',
  'amber+strict': 'Share within your organization only.',
  red: 'Named recipients only; does not leave this application.',
}

export const TLP_UNSPECIFIED_MEANING =
  'No sharing policy has been recorded for this input yet.'

export const TLP_LABELS: Record<Tlp, string> = {
  clear: 'TLP:CLEAR',
  green: 'TLP:GREEN',
  amber: 'TLP:AMBER',
  'amber+strict': 'TLP:AMBER+STRICT',
  red: 'TLP:RED',
}

export const TLP_SELECT_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Unspecified' },
  ...TLP_VALUES.map((v) => ({ value: v, label: TLP_LABELS[v] })),
]

export const TLP_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Any TLP' },
  { value: 'unspecified', label: 'Unspecified' },
  ...TLP_VALUES.map((v) => ({ value: v, label: TLP_LABELS[v] })),
]

export const DESTINATION_OPTIONS: { value: ExportDestination; label: string }[] = [
  { value: 'internal', label: 'Internal (SIEM / firewall)' },
  { value: 'community', label: 'Community sharing' },
  { value: 'public', label: 'Public release' },
]

export const DESTINATION_HELP: Record<ExportDestination, string> = {
  internal:
    'Allows Unspecified, TLP:CLEAR, GREEN, AMBER, and AMBER+STRICT. TLP:RED never leaves the application.',
  community: 'Allows TLP:CLEAR and TLP:GREEN only. TLP:RED never leaves the application.',
  public: 'Allows TLP:CLEAR only. TLP:RED never leaves the application.',
}

export function parseTlpSelectValue(value: string): Tlp | null {
  if (!value) return null
  return value as Tlp
}

export function formatTlpSelectValue(tlp: Tlp | null | undefined): string {
  return tlp ?? ''
}

/** True when changing a feed/report marking requires `tlp_change_reason`. */
export function needsTlpChangeReason(previous: Tlp | null, next: Tlp | null): boolean {
  const prev = previous ?? null
  const nxt = next ?? null
  if (prev === nxt) return false
  if (prev !== null && nxt === null) return true
  if (prev !== null && nxt !== null && TLP_RANK[nxt] < TLP_RANK[prev]) return true
  return false
}

const NOT_ALLOWED = "isn't allowed for this destination"

const EXCLUSION_PHRASES: Record<keyof ExcludedByTlpCounts, string> = {
  unspecified: 'Unspecified markings are allowed for internal destinations only',
  clear: `TLP:CLEAR ${NOT_ALLOWED}`,
  green: `TLP:GREEN ${NOT_ALLOWED}`,
  amber: `TLP:AMBER ${NOT_ALLOWED}`,
  'amber+strict': `TLP:AMBER+STRICT ${NOT_ALLOWED}`,
  red: 'TLP:RED never leaves the application',
}

/** Human-readable preview lines for `excluded_by_tlp` counts. */
export function formatExcludedByTlp(excluded: ExcludedByTlpCounts): string[] {
  const lines: string[] = []
  for (const key of Object.keys(EXCLUSION_PHRASES) as (keyof ExcludedByTlpCounts)[]) {
    const count = excluded[key]
    if (count <= 0) continue
    const noun = count === 1 ? 'indicator' : 'indicators'
    lines.push(`${count} ${noun} excluded: ${EXCLUSION_PHRASES[key]}`)
  }
  return lines
}

export function tlpSourceLabel(kind: string, name: string): string {
  if (kind === 'manual') return 'Manual entry'
  return name
}
