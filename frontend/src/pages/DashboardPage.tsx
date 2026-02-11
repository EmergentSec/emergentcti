import { useQuery } from '@tanstack/react-query';
import { getDashboardStats } from '@/api/search';
import { StatsGrid } from '@/components/dashboard/StatsGrid';
import { TypeDistribution } from '@/components/dashboard/TypeDistribution';
import { FeedHealthPanel } from '@/components/dashboard/FeedHealthPanel';
import { ObservableTrend } from '@/components/dashboard/ObservableTrend';
import { TLPDistribution } from '@/components/dashboard/TLPDistribution';
import { TopTags } from '@/components/dashboard/TopTags';
import {
  useObservableTrend,
  useTLPDistribution,
  useTopTags,
} from '@/hooks/useDashboard';

export function DashboardPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: getDashboardStats,
    staleTime: 30_000,
  });

  const { data: trendData, isLoading: trendLoading } = useObservableTrend();
  const { data: tlpData, isLoading: tlpLoading } = useTLPDistribution();
  const { data: tagsData, isLoading: tagsLoading } = useTopTags();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Threat intelligence overview and feed activity
        </p>
      </div>

      <StatsGrid stats={stats} isLoading={isLoading} />

      <div className="grid gap-6 lg:grid-cols-2">
        <TypeDistribution
          data={stats?.observables_by_type}
          isLoading={isLoading}
        />
        <FeedHealthPanel
          runs={stats?.recent_feed_runs}
          isLoading={isLoading}
        />
      </div>

      <ObservableTrend data={trendData} isLoading={trendLoading} />

      <div className="grid gap-6 lg:grid-cols-2">
        <TLPDistribution data={tlpData} isLoading={tlpLoading} />
        <TopTags data={tagsData} isLoading={tagsLoading} />
      </div>
    </div>
  );
}
