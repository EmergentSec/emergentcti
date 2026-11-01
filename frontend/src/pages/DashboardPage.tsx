import { useDashboard } from '@/hooks/useDashboard'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
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
      <EmptyState
        className="[&_h3]:text-destructive"
        title="Failed to load dashboard stats"
        description={error instanceof Error ? error.message : 'Unknown error'}
      />
    )
  }

  return (
    <div className="space-y-5">
      <KpiCards stats={data} />

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <IngestionTrend series={data.daily_ingest_14d} />
        </div>
        <div className="lg:col-span-1">
          <TypeDonut byType={data.by_type} total={data.total_observables} />
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
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
