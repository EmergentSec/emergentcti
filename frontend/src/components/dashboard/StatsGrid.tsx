import { Card, CardContent } from '@/components/ui/Card'

interface StatCardProps {
  label: string
  value: number | string
  icon: React.ReactNode
}

function StatCard({ label, value, icon }: StatCardProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{label}</p>
            <p className="mt-1 text-3xl font-bold text-foreground tabular-nums">
              {typeof value === 'number' ? value.toLocaleString() : value}
            </p>
          </div>
          <div className="text-muted-foreground">{icon}</div>
        </div>
      </CardContent>
    </Card>
  )
}

interface StatsGridProps {
  totalObservables: number
  activeFeeds: number
  todayIngest: number
  feedErrors: number
}

export function StatsGrid({ totalObservables, activeFeeds, todayIngest, feedErrors }: StatsGridProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        label="Total Observables"
        value={totalObservables}
        icon={
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="9" />
            <circle cx="12" cy="12" r="4" />
            <line x1="12" y1="3" x2="12" y2="1" />
            <line x1="12" y1="23" x2="12" y2="21" />
            <line x1="3" y1="12" x2="1" y2="12" />
            <line x1="23" y1="12" x2="21" y2="12" />
          </svg>
        }
      />
      <StatCard
        label="Active Feeds"
        value={activeFeeds}
        icon={
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 4v16h16" />
            <path d="M8 16l4-4 4 3 4-5" />
          </svg>
        }
      />
      <StatCard
        label="Today's Ingest"
        value={todayIngest}
        icon={
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2v10" />
            <path d="M8 8l4 4 4-4" />
            <path d="M4 14h16v6H4z" />
          </svg>
        }
      />
      <StatCard
        label="Feed Errors (24h)"
        value={feedErrors}
        icon={
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        }
      />
    </div>
  )
}
