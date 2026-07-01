export interface ConfidenceDecayConfig {
  confidence_decay_enabled: boolean
  confidence_decay_days: number
  confidence_decay_rate: number
  confidence_decay_floor: number
  confidence_decay_interval_hours: number
}

/** @deprecated Use ConfidenceDecayConfig instead */
export type GlobalConfig = ConfidenceDecayConfig

export interface InstanceConfig extends ConfidenceDecayConfig {
  instance_name: string
  observable_retention_days: number
  default_export_format: string
}
