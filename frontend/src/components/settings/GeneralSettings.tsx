import { useQuery } from '@tanstack/react-query'
import { getConfig } from '@/api/settings'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

interface SettingRowProps {
  label: string
  value: string | number | boolean
  description?: string
}

function SettingRow({ label, value, description }: SettingRowProps) {
  const displayValue = typeof value === 'boolean' ? (value ? 'Enabled' : 'Disabled') : String(value)

  return (
    <div className="flex items-center justify-between py-3 border-b border-border last:border-0">
      <div>
        <p className="text-sm font-medium text-foreground">{label}</p>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      <span className="text-sm font-mono tabular-nums text-muted-foreground">
        {displayValue}
      </span>
    </div>
  )
}

export function GeneralSettings() {
  const { data: config, isLoading, error } = useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Confidence Decay Settings</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : error ? (
          <p className="text-sm text-destructive-foreground">Failed to load configuration</p>
        ) : config ? (
          <div>
            <SettingRow
              label="Decay Enabled"
              value={config.confidence_decay_enabled}
              description="Whether confidence scores decay over time without re-sighting"
            />
            <SettingRow
              label="Decay Starts After"
              value={`${config.confidence_decay_days} days`}
              description="Days without re-sighting before decay begins"
            />
            <SettingRow
              label="Decay Rate"
              value={`${config.confidence_decay_rate} points/week`}
              description="How many confidence points are lost per week of staleness"
            />
            <SettingRow
              label="Decay Floor"
              value={config.confidence_decay_floor}
              description="Minimum confidence score (never decays below this)"
            />
            <SettingRow
              label="Decay Check Interval"
              value={`${config.confidence_decay_interval_hours} hours`}
              description="How often the decay job runs"
            />

            <p className="mt-4 text-xs text-muted-foreground">
              These settings are configured via environment variables. Restart the API service after changing.
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
