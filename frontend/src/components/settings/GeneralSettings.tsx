import { useQuery } from '@tanstack/react-query'
import { getConfig } from '@/api/settings'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import type { InstanceConfig } from '@/types/settings'

interface SettingRowProps {
  label: string
  value: string
  mono?: boolean
}

function SettingRow({ label, value, mono = false }: SettingRowProps) {
  return (
    <div className="flex items-start justify-between border-b border-border py-3 last:border-0">
      <p className="text-sm text-muted-foreground">{label}</p>
      <span className={mono ? 'font-mono text-sm text-foreground' : 'text-sm text-foreground'}>
        {value}
      </span>
    </div>
  )
}

function decayLabel(config: InstanceConfig): string {
  if (!config.confidence_decay_enabled) return 'Disabled'
  return `-${config.confidence_decay_rate}/wk after ${config.confidence_decay_days}d, floor ${config.confidence_decay_floor}`
}

export function GeneralSettings() {
  const { data: config, isLoading, error } = useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>General</CardTitle>
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
            <SettingRow label="Instance name" value={config.instance_name} />
            <SettingRow label="Confidence decay" value={decayLabel(config)} mono />
            <SettingRow
              label="Observable retention"
              value={`${config.observable_retention_days} days`}
              mono
            />
            <SettingRow label="Default export format" value={config.default_export_format} />

            <p className="mt-4 text-xs text-muted-foreground">
              Configured via environment; restart to change.
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
