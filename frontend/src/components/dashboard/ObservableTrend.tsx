import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { TrendDataPoint } from '@/hooks/useDashboard';

interface ObservableTrendProps {
  data: TrendDataPoint[] | undefined;
  isLoading?: boolean;
}

export function ObservableTrend({ data, isLoading }: ObservableTrendProps) {
  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Observable Trend (30 days)</CardTitle>
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
          <CardTitle className="text-base">Observable Trend (30 days)</CardTitle>
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
        <CardTitle className="text-base">Observable Trend (30 days)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(217.2 32.6% 17.5%)"
              />
              <XAxis
                dataKey="date"
                tick={{ fill: 'hsl(215 20.2% 65.1%)', fontSize: 12 }}
                axisLine={{ stroke: 'hsl(217.2 32.6% 17.5%)' }}
                tickFormatter={(value: string) => {
                  const d = new Date(value);
                  return `${d.getMonth() + 1}/${d.getDate()}`;
                }}
              />
              <YAxis
                tick={{ fill: 'hsl(215 20.2% 65.1%)', fontSize: 12 }}
                axisLine={{ stroke: 'hsl(217.2 32.6% 17.5%)' }}
                allowDecimals={false}
              />
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
                labelFormatter={(label: string) => {
                  const d = new Date(label);
                  return d.toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  });
                }}
              />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#a855f7"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#a855f7' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
