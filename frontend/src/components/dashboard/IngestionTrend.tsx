import {
  AreaChart,
  Area,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'

interface IngestionTrendProps {
  series: { date: string; count: number }[]
}

export function IngestionTrend({ series }: IngestionTrendProps) {
  const total = series.reduce((sum, p) => sum + p.count, 0)

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle>Ingestion volume</CardTitle>
            <CardDescription className="mt-1">
              New observables per day · last 14 days
            </CardDescription>
          </div>
          <p className="shrink-0 font-mono text-xl font-bold leading-none text-foreground">
            {total.toLocaleString()}
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">total</span>
          </p>
        </div>
      </CardHeader>
      <CardContent className="px-0 pb-3">
        <div className="h-[190px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={series} margin={{ top: 4, right: 16, bottom: 0, left: 16 }}>
              <defs>
                <linearGradient id="ingestion-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--brand)" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="var(--brand)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" hide />
              <Tooltip
                contentStyle={{
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: '6px',
                  fontSize: '12px',
                  color: 'var(--foreground)',
                }}
                labelStyle={{ color: 'var(--muted-foreground)' }}
                cursor={{ stroke: 'var(--border-strong)', strokeWidth: 1 }}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="var(--brand)"
                strokeWidth={2}
                fill="url(#ingestion-grad)"
                dot={false}
                activeDot={{ r: 3, fill: 'var(--brand)', strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
