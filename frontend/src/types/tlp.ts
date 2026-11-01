/** FIRST TLP 2.0 values stored on the API (exact strings). */
export type Tlp = 'clear' | 'green' | 'amber' | 'amber+strict' | 'red'

/** Filter query value for effective / entity marking (`unspecified` = JSON null). */
export type TlpFilterValue = Tlp | 'unspecified'

export type TlpSourceKind = 'feed' | 'report' | 'manual'

export interface TlpSource {
  kind: TlpSourceKind
  id: string | null
  name: string
  tlp: Tlp | null
}

export interface TlpOverride {
  tlp: Tlp
  reason: string
  set_at: string
  set_by: string | null
}

export type ExportDestination = 'internal' | 'community' | 'public'

export type ExcludedByTlpCounts = {
  unspecified: number
  clear: number
  green: number
  amber: number
  'amber+strict': number
  red: number
}
