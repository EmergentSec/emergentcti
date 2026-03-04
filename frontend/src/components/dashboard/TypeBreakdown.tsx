import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { typeColors, typeLabels } from '@/lib/utils'

interface TypeBreakdownProps {
  byType: Record<string, number>
  total: number
}

const typeOrder = ['ip-addr', 'domain-name', 'url', 'file-hash', 'email-addr', 'command-line']

export function TypeBreakdown({ byType, total }: TypeBreakdownProps) {
  const sortedTypes = typeOrder.filter((t) => t in byType || true)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Observable Types</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {sortedTypes.map((type) => {
            const count = byType[type] || 0
            const pct = total > 0 ? (count / total) * 100 : 0
            const label = typeLabels[type] || type

            return (
              <div key={type} className="space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge className={typeColors[type]}>{label}</Badge>
                  </div>
                  <span className="text-sm font-medium tabular-nums text-foreground">
                    {count.toLocaleString()}
                  </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-muted">
                  <div
                    className="h-1.5 rounded-full bg-primary transition-all duration-500"
                    style={{ width: `${Math.max(pct, 0.5)}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>

        {total === 0 && (
          <p className="text-center text-sm text-muted-foreground py-4">
            No observables ingested yet
          </p>
        )}
      </CardContent>
    </Card>
  )
}
