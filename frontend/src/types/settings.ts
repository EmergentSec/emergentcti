export interface ConfidenceDecayConfig {
  confidence_decay_enabled: boolean
  confidence_decay_days: number
  confidence_decay_rate: number
  confidence_decay_floor: number
  confidence_decay_interval_hours: number
}

/** @deprecated Use ConfidenceDecayConfig instead */
export type GlobalConfig = ConfidenceDecayConfig
