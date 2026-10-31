import { CrosshairSimple, Rss, DownloadSimple, Warning } from '@phosphor-icons/react'
import { Card, CardContent } from '@/components/ui/Card'
import { vsAvgDelta } from '@/lib/dashboardFormat'
import type { DashboardStats } from '@/types/dashboard'

interface KpiCardsProps {
  stats: DashboardStats
}

interface KpiCardProps {
  label: string
  value: string
  icon: React.ReactNode
  iconTone: string
  subtitle?: React.ReactNode
}

function KpiCard({ label, value, icon, iconTone, subtitle }: KpiCardProps) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <p className="text-sm text-muted-foreground">{label}</p>
          <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${iconTone}`}>
            {icon}
          </div>
        </div>
        <p className="mt-3 font-mono text-2xl font-bold leading-none tracking-tight text-foreground">
          {value}
        </p>
        {subtitle && (
          <div className="mt-2 text-xs">{subtitle}</div>
        )}
      </CardContent>
    </Card>
  )
}

export function KpiCards({ stats }: KpiCardsProps) {
  const {
    total_observables,
    total_feeds,
    feeds_enabled,
    last_24h_ingested,
    feed_errors_24h,
    feeds_health,
    daily_ingest_14d,
  } = stats

  // Card 3: vs avg delta
  const delta = vsAvgDelta(last_24h_ingested, daily_ingest_14d)
  const deltaSubtitle =
    delta !== null ? (
      <span className={delta >= 0 ? 'text-cat-green' : 'text-conf-critical'}>
        {delta >= 0 ? '▲' : '▼'} {Math.abs(delta)}% vs avg
      </span>
    ) : null

  // Card 4: feed error subtitle
  const failingFeed =
    feed_errors_24h > 0
      ? feeds_health.find((f) => f.last_run_status === 'failure')
      : null
  const errorSubtitle =
    feed_errors_24h > 0 ? (
      failingFeed ? (
        <span className="text-muted-foreground">↳ {failingFeed.name} failed</span>
      ) : (
        <span className="text-muted-foreground">{feed_errors_24h} feed error(s)</span>
      )
    ) : (
      <span className="text-cat-green">all healthy</span>
    )

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <KpiCard
        label="Total observables"
        value={total_observables.toLocaleString()}
        icon={<CrosshairSimple size={16} weight="bold" />}
        iconTone="bg-primary-soft text-primary"
        subtitle={
          <span className="text-muted-foreground">indicators tracked</span>
        }
      />
      <KpiCard
        label="Active feeds"
        value={`${feeds_enabled} / ${total_feeds}`}
        icon={<Rss size={16} weight="bold" />}
        iconTone="bg-cat-blue/10 text-cat-blue"
        subtitle={
          <span className="text-muted-foreground">
            {total_feeds - feeds_enabled} disabled
          </span>
        }
      />
      <KpiCard
        label="Ingested (24h)"
        value={last_24h_ingested.toLocaleString()}
        icon={<DownloadSimple size={16} weight="bold" />}
        iconTone="bg-success-soft text-success-ink"
        subtitle={deltaSubtitle}
      />
      <KpiCard
        label="Feed errors (24h)"
        value={String(feed_errors_24h)}
        icon={<Warning size={16} weight="bold" />}
        iconTone="bg-destructive-soft text-destructive-ink"
        subtitle={errorSubtitle}
      />
    </div>
  )
}
