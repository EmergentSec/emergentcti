import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { TLPDataPoint } from '@/hooks/useDashboard';

interface TLPDistributionProps {
  data: TLPDataPoint[] | undefined;
  isLoading?: boolean;
}

const TLP_CHART_COLORS: Record<string, string> = {
  clear: '#e2e8f0',
  green: '#22c55e',
  amber: '#f59e0b',
  'amber+strict': '#f97316',
  red: '#ef4444',
};

function tlpLabel(tlp: string): string {
  return `TLP:${tlp.toUpperCase()}`;
}

export function TLPDistribution({ data, isLoading }: TLPDistributionProps) {
  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">TLP Distribution</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] animate-pulse rounded bg-muted" />
        </CardContent>
      </Card>
    );
  }

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">TLP Distribution</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-[300px] items-center justify-center text-muted-foreground">
            No data available
          </div>
        </CardContent>
      </Card>
    );
  }

  const chartData = data.map((d) => ({
    name: tlpLabel(d.tlp),
    value: d.count,
    tlp: d.tlp,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">TLP Distribution</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                dataKey="value"
                nameKey="name"
                paddingAngle={2}
              >
                {chartData.map((entry) => (
                  <Cell
                    key={entry.tlp}
                    fill={TLP_CHART_COLORS[entry.tlp] || '#6b7280'}
                    stroke="transparent"
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(222.2 84% 6.5%)',
                  border: '1px solid hsl(217.2 32.6% 17.5%)',
                  borderRadius: '8px',
                  color: 'hsl(210 40% 98%)',
                }}
                formatter={(value: number) => [
                  value.toLocaleString(),
                  'Observables',
                ]}
              />
              <Legend
                wrapperStyle={{
                  color: 'hsl(215 20.2% 65.1%)',
                  fontSize: '12px',
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
