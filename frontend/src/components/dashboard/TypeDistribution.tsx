import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { OBSERVABLE_TYPE_LABELS } from '@/lib/utils';

interface TypeDistributionProps {
  data: Record<string, number> | undefined;
  isLoading?: boolean;
}

const CHART_COLORS: Record<string, string> = {
  'ip-addr': '#a855f7',
  'domain-name': '#06b6d4',
  'url': '#22c55e',
  'file-hash': '#f59e0b',
  'email-addr': '#ec4899',
  'command-line': '#6b7280',
  'user-agent': '#9ca3af',
  'certificate': '#78716c',
  'asn': '#64748b',
  'cidr': '#94a3b8',
};

export function TypeDistribution({ data, isLoading }: TypeDistributionProps) {
  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Observable Types</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] animate-pulse rounded bg-muted" />
        </CardContent>
      </Card>
    );
  }

  const chartData = Object.entries(data)
    .filter(([, count]) => count > 0)
    .map(([type, count]) => ({
      name: OBSERVABLE_TYPE_LABELS[type] || type,
      value: count,
      type,
    }))
    .sort((a, b) => b.value - a.value);

  if (chartData.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Observable Types</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-[300px] items-center justify-center text-muted-foreground">
            No data available
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Observable Types</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                horizontal={false}
                stroke="hsl(217.2 32.6% 17.5%)"
              />
              <XAxis
                type="number"
                tick={{ fill: 'hsl(215 20.2% 65.1%)', fontSize: 12 }}
                axisLine={{ stroke: 'hsl(217.2 32.6% 17.5%)' }}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={75}
                tick={{ fill: 'hsl(215 20.2% 65.1%)', fontSize: 12 }}
                axisLine={{ stroke: 'hsl(217.2 32.6% 17.5%)' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(222.2 84% 6.5%)',
                  border: '1px solid hsl(217.2 32.6% 17.5%)',
                  borderRadius: '8px',
                  color: 'hsl(210 40% 98%)',
                }}
                formatter={(value: number) => [value.toLocaleString(), 'Count']}
                labelFormatter={(label: string) => label}
                cursor={{ fill: 'hsl(217.2 32.6% 17.5%)', opacity: 0.3 }}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.type}
                    fill={CHART_COLORS[entry.type] || '#6b7280'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
