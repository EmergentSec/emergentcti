import {
  AreaChart,
  Area,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
} from 'recharts'
import { Card, CardContent, CardHeader } from '@/components/ui/Card'

interface DecayChartProps {
  nativeMax: number
  ageDays: number
  decayDays: number
  decayRate: number
  decayFloor: number
}

/**
 * Linear decay projection — exported for unit testing.
 *
 * Model: score is flat at nativeMax until decayDays have elapsed.
 * After that, it drops by decayRate per completed week (minimum 1 week
 * of decay when d > decayDays), flooring at decayFloor.
 *
 * NOT half-life: decay is linear (fixed points-per-week), not exponential.
 */
export function projectDecayScore(
  d: number,
  nativeMax: number,
  decayDays: number,
  decayRate: number,
  decayFloor: number,
): number {
  if (d <= decayDays) return nativeMax
  const weeksElapsed = Math.max(1, Math.floor((d - decayDays) / 7))
  return Math.max(decayFloor, nativeMax - weeksElapsed * decayRate)
}

export function DecayChart({
  nativeMax,
  ageDays,
  decayDays,
  decayRate,
  decayFloor,
}: DecayChartProps) {
  const maxDay =
    decayDays + Math.ceil(Math.max(1, (nativeMax - decayFloor) / decayRate)) * 7 + 7

  const data: { day: number; score: number }[] = []
  for (let d = 0; d <= maxDay; d++) {
    data.push({
      day: d,
      score: projectDecayScore(d, nativeMax, decayDays, decayRate, decayFloor),
    })
  }

  const caption = `−${decayRate}/wk after ${decayDays}d`

  return (
    <Card>
      <CardHeader className="pb-2 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-foreground">Confidence decay</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground">
              Score decays from native as the indicator ages without re-sighting
            </p>
          </div>
          <span
            className="shrink-0 font-mono text-[11px] text-muted-foreground"
            data-testid="decay-caption"
          >
            {caption}
          </span>
        </div>
      </CardHeader>
      <CardContent className="px-0 pb-2">
        <div className="h-[160px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 16 }}>
              <defs>
                <linearGradient id="decay-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--brand)" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="var(--brand)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="day" hide />
              <YAxis domain={[0, nativeMax]} hide />
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
                formatter={(value) => [value, 'Score']}
                labelFormatter={(label) => `Day ${label}`}
              />
              {ageDays <= maxDay && (
                <ReferenceLine
                  x={ageDays}
                  stroke="var(--brand)"
                  strokeDasharray="3 3"
                  strokeWidth={1.5}
                />
              )}
              <Area
                type="monotone"
                dataKey="score"
                stroke="var(--brand)"
                strokeWidth={2}
                fill="url(#decay-grad)"
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
