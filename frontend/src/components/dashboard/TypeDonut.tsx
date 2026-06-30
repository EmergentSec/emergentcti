import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import { Card, CardContent, CardHeader } from '@/components/ui/Card'
import { pct } from '@/lib/dashboardFormat'
import { typeLabels } from '@/lib/utils'

interface TypeDonutProps {
  byType: Record<string, number>
  total: number
}

// Legend order matching the screenshot
const TYPE_ORDER = [
  'ip-addr',
  'url',
  'domain-name',
  'file-hash',
  'email-addr',
  'command-line',
] as const

// CSS variable color values for recharts (can't use className)
const TYPE_COLORS: Record<string, string> = {
  'ip-addr': 'var(--cat-blue)',
  'url': 'var(--cat-green)',
  'domain-name': 'var(--cat-purple)',
  'file-hash': 'var(--cat-orange)',
  'email-addr': 'var(--cat-pink)',
  'command-line': 'var(--cat-yellow)',
}

// Dot color swatch using inline style (so CSS vars resolve at runtime)
function ColorDot({ type }: { type: string }) {
  return (
    <span
      className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
      style={{ background: TYPE_COLORS[type] }}
    />
  )
}

export function TypeDonut({ byType, total }: TypeDonutProps) {
  const data = TYPE_ORDER.map((type) => ({
    type,
    count: byType[type] ?? 0,
    color: TYPE_COLORS[type],
    label: typeLabels[type] ?? type,
  }))

  return (
    <Card>
      <CardHeader className="pb-2 p-5">
        <h3 className="text-base font-semibold text-foreground">Observable types</h3>
        <p className="text-[12px] text-muted-foreground">By indicator class</p>
      </CardHeader>
      <CardContent className="p-5 pt-0">
        <div className="flex items-center gap-6">
          {/* Donut chart with center label */}
          <div className="relative h-[180px] w-[180px] shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  cx="50%"
                  cy="50%"
                  innerRadius={54}
                  outerRadius={80}
                  dataKey="count"
                  startAngle={90}
                  endAngle={-270}
                  strokeWidth={2}
                  stroke="var(--card)"
                >
                  {data.map((entry) => (
                    <Cell key={entry.type} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            {/* Center label — positioned absolutely over the chart */}
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-mono text-[20px] font-extrabold leading-none text-foreground">
                {total.toLocaleString()}
              </span>
              <span className="mt-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                types
              </span>
            </div>
          </div>

          {/* Legend */}
          <div className="flex flex-1 flex-col gap-1.5">
            {data.map((entry) => (
              <div key={entry.type} className="flex items-center gap-2">
                <ColorDot type={entry.type} />
                <span className="flex-1 text-[13px] text-foreground">{entry.label}</span>
                <span className="font-mono text-[13px] text-muted-foreground">
                  {pct(entry.count, total)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
