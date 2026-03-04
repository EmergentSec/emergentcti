import { Fragment, useState } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { Badge } from '@/components/ui/Badge'
import { ObservableExpandedRow } from './ObservableExpandedRow'
import { cn, typeColors, typeLabels, confidenceColor, formatRelativeTime } from '@/lib/utils'
import type { Observable } from '@/types/observable'

interface ObservableTableProps {
  observables: Observable[]
}

function ConfidenceMeter({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full bg-muted">
        <div
          className={cn(
            'h-1.5 rounded-full transition-all',
            score >= 80 ? 'bg-red-500' :
            score >= 60 ? 'bg-orange-500' :
            score >= 40 ? 'bg-yellow-500' : 'bg-gray-500'
          )}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={cn('text-sm tabular-nums font-medium', confidenceColor(score))}>
        {score}
      </span>
    </div>
  )
}

export function ObservableTable({ observables }: ObservableTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const toggleExpanded = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-8" />
          <TableHead className="w-28">Type</TableHead>
          <TableHead>Value</TableHead>
          <TableHead className="w-32">Confidence</TableHead>
          <TableHead className="w-44 text-right">Sources</TableHead>
          <TableHead className="w-28 text-right">Last Seen</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {observables.map((obs) => {
          const isExpanded = expandedId === obs.id
          return (
            <Fragment key={obs.id}>
              <TableRow
                className="group cursor-pointer hover:bg-muted/50 transition-colors"
                tabIndex={0}
                role="button"
                onClick={() => toggleExpanded(obs.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    toggleExpanded(obs.id)
                  }
                }}
              >
                <TableCell className="w-8 text-muted-foreground">
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 14 14"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    className={cn(
                      'transition-transform duration-200',
                      isExpanded && 'rotate-90'
                    )}
                  >
                    <path d="M5 3l4 4-4 4" />
                  </svg>
                </TableCell>
                <TableCell>
                  <Badge className={typeColors[obs.type]}>
                    {typeLabels[obs.type] || obs.type}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-sm max-w-0 truncate">
                  {obs.value}
                </TableCell>
                <TableCell>
                  <ConfidenceMeter score={obs.confidence_score} />
                </TableCell>
                <TableCell className="text-right text-sm text-muted-foreground">
                  {obs.sources.length === 0 ? (
                    <span className="inline-flex items-center rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
                      Manual
                    </span>
                  ) : (
                    <span className="inline-flex flex-wrap justify-end gap-1">
                      {obs.sources.slice(0, 2).map((s) => (
                        <span
                          key={s.feed_id}
                          className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-xs"
                        >
                          {s.feed_name}
                        </span>
                      ))}
                      {obs.sources.length > 2 && (
                        <span className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-xs">
                          +{obs.sources.length - 2}
                        </span>
                      )}
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-right text-sm text-muted-foreground whitespace-nowrap">
                  {formatRelativeTime(obs.last_seen)}
                </TableCell>
              </TableRow>
              {isExpanded && (
                <TableRow>
                  <TableCell colSpan={6} className="p-0 border-t border-border bg-muted/20">
                    <ObservableExpandedRow sources={obs.sources} />
                  </TableCell>
                </TableRow>
              )}
            </Fragment>
          )
        })}
      </TableBody>
    </Table>
  )
}
