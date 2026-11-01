import type { ExcludedByTlpCounts } from '@/types/tlp'

export const EMPTY_TLP_OBSERVABLE_FIELDS = {
  tags: [] as string[],
  manual_tlp: null,
  effective_tlp: null,
  tlp_sources: [],
  tlp_override: null,
}

export const EMPTY_TLP_REPORT_FIELDS = {
  tlp: null,
  tags: [] as string[],
}

export const ZERO_EXCLUDED_BY_TLP: ExcludedByTlpCounts = {
  unspecified: 0,
  clear: 0,
  green: 0,
  amber: 0,
  'amber+strict': 0,
  red: 0,
}
