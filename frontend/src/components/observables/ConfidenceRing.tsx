import { Card, CardContent, CardHeader } from '@/components/ui/Card'

interface ConfidenceRingProps {
  decayed: number
  nativeMax: number
}

function getBandColor(score: number): string {
  if (score >= 80) return 'var(--conf-critical)'
  if (score >= 60) return 'var(--conf-high)'
  if (score >= 40) return 'var(--conf-medium)'
  return 'var(--conf-low)'
}

export function ConfidenceRing({ decayed, nativeMax }: ConfidenceRingProps) {
  const color = getBandColor(decayed)
  const R = 38
  const circumference = 2 * Math.PI * R
  const clamped = Math.max(0, Math.min(100, decayed))
  const dashOffset = circumference * (1 - clamped / 100)

  return (
    <Card>
      <CardHeader className="pb-3 p-5">
        <h3 className="text-base font-semibold text-foreground">Effective confidence</h3>
      </CardHeader>
      <CardContent className="p-5 pt-0 flex flex-col items-center">
        {/* SVG donut ring */}
        <div className="relative h-[120px] w-[120px]">
          <svg
            viewBox="0 0 100 100"
            className="h-full w-full -rotate-90"
            aria-hidden="true"
          >
            {/* Background track */}
            <circle
              cx={50}
              cy={50}
              r={R}
              fill="none"
              stroke="var(--border)"
              strokeWidth={9}
            />
            {/* Filled arc */}
            <circle
              cx={50}
              cy={50}
              r={R}
              fill="none"
              stroke={color}
              strokeWidth={9}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
            />
          </svg>
          {/* Center number — absolute overlay */}
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <span
              className="font-mono text-3xl font-extrabold leading-none"
              style={{ color }}
              data-testid="ring-center"
            >
              {decayed}
            </span>
          </div>
        </div>

        {/* Dual readout below ring */}
        <div className="mt-4 flex items-end gap-6">
          <div className="text-center">
            <span className="block text-[11px] uppercase tracking-widest text-muted-foreground">
              decayed
            </span>
            <span
              className="font-mono text-xl font-bold tabular-nums"
              style={{ color }}
              data-testid="readout-decayed"
            >
              {decayed}
            </span>
          </div>
          <div className="text-center">
            <span className="block text-[11px] uppercase tracking-widest text-muted-foreground">
              native max
            </span>
            <span
              className="font-mono text-xl font-bold tabular-nums text-muted-foreground"
              data-testid="readout-native"
            >
              {nativeMax}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
