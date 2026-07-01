import { useDashboard } from '@/hooks/useDashboard'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { KpiCards } from '@/components/dashboard/KpiCards'
import { IngestionTrend } from '@/components/dashboard/IngestionTrend'
import { TypeDonut } from '@/components/dashboard/TypeDonut'
import { FeedStatusTable } from '@/components/dashboard/FeedStatusTable'
import { ConfidenceBars } from '@/components/dashboard/ConfidenceBars'

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboard()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <p className="text-destructive-foreground">Failed to load dashboard stats</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {error instanceof Error ? error.message : 'Unknown error'}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3.5">
      <KpiCards stats={data} />

      <div className="grid lg:grid-cols-3 gap-3.5">
        <div className="lg:col-span-2">
          <IngestionTrend series={data.daily_ingest_14d} />
        </div>
        <div className="lg:col-span-1">
          <TypeDonut byType={data.by_type} total={data.total_observables} />
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-3.5">
        <div className="lg:col-span-2">
          <FeedStatusTable feeds={data.feeds_health} />
        </div>
        <div className="lg:col-span-1">
          <ConfidenceBars distribution={data.confidence_distribution} />
        </div>
      </div>
    </div>
  )
}
