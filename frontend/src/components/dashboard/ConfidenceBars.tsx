import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';

interface Distribution {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

interface ConfidenceBarsProps {
  distribution: Distribution;
}

const BANDS = [
  { key: 'critical' as const, label: 'Critical', range: '80–100', barColor: 'bg-conf-critical' },
  { key: 'high'     as const, label: 'High',     range: '60–79',  barColor: 'bg-conf-high'     },
  { key: 'medium'   as const, label: 'Medium',   range: '40–59',  barColor: 'bg-conf-medium'   },
  { key: 'low'      as const, label: 'Low',      range: '0–39',   barColor: 'bg-conf-low'      },
];

export function ConfidenceBars({ distribution }: ConfidenceBarsProps) {
  const counts = BANDS.map((b) => distribution[b.key]);
  const max = Math.max(...counts, 1); // avoid division by zero

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-[15px]">Confidence distribution</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {BANDS.map((band) => {
          const count = distribution[band.key];
          const fillPct = Math.round((count / max) * 100);

          return (
            <div key={band.key} className="space-y-1">
              <div className="flex items-center justify-between text-[13px]">
                <span className="flex items-center gap-1.5">
                  <span className="font-medium text-foreground">{band.label}</span>
                  <span className="text-muted-foreground">{band.range}</span>
                </span>
                <span className="font-mono text-[12px] text-foreground">{count}</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface3">
                <div
                  className={`h-full rounded-full ${band.barColor}`}
                  style={{ width: `${fillPct}%` }}
                />
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
