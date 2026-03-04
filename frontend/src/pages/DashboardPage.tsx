import { useDashboard } from '@/hooks/useDashboard'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { StatsGrid } from '@/components/dashboard/StatsGrid'
import { TypeBreakdown } from '@/components/dashboard/TypeBreakdown'
import { RecentFeedRuns } from '@/components/dashboard/RecentFeedRuns'

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

  const feedErrors = data.feeds_health.filter(
    (f) => f.last_run_status === 'failure'
  ).length

  return (
    <div className="space-y-6">
      <StatsGrid
        totalObservables={data.total_observables}
        activeFeeds={data.feeds_enabled}
        todayIngest={data.last_24h_ingested}
        feedErrors={feedErrors}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <TypeBreakdown byType={data.by_type} total={data.total_observables} />
        </div>
        <div className="lg:col-span-2">
          <RecentFeedRuns feeds={data.feeds_health} />
        </div>
      </div>
    </div>
  )
}
