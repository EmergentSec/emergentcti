import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { TagDataPoint } from '@/hooks/useDashboard';

interface TopTagsProps {
  data: TagDataPoint[] | undefined;
  isLoading?: boolean;
}

export function TopTags({ data, isLoading }: TopTagsProps) {
  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Top Tags</CardTitle>
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
          <CardTitle className="text-base">Top Tags</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-[300px] items-center justify-center text-muted-foreground">
            No tags available
          </div>
        </CardContent>
      </Card>
    );
  }

  const chartData = data.map((d) => ({
    name: d.tag,
    value: d.count,
  }));

  const chartHeight = Math.max(300, chartData.length * 28);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Top Tags</CardTitle>
      </CardHeader>
      <CardContent>
        <div style={{ height: chartHeight }}>
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
                allowDecimals={false}
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
                formatter={(value: number) => [
                  value.toLocaleString(),
                  'Observables',
                ]}
                labelFormatter={(label: string) => label}
                cursor={{ fill: 'hsl(217.2 32.6% 17.5%)', opacity: 0.3 }}
              />
              <Bar
                dataKey="value"
                fill="#06b6d4"
                radius={[0, 4, 4, 0]}
                barSize={20}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
