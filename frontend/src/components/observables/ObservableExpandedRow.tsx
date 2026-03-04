import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { formatDate, confidenceColor } from '@/lib/utils'
import type { ObservableSource } from '@/types/observable'

interface ObservableExpandedRowProps {
  sources: ObservableSource[]
}

export function ObservableExpandedRow({ sources }: ObservableExpandedRowProps) {
  if (sources.length === 0) {
    return (
      <div className="px-4 py-3 text-sm text-muted-foreground">
        Manually added observable — no feed sources
      </div>
    )
  }

  return (
    <div className="px-4 py-3">
      <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        Sources ({sources.length})
      </p>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Feed</TableHead>
            <TableHead>Confidence</TableHead>
            <TableHead>First Seen</TableHead>
            <TableHead>Last Seen</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sources.map((source) => (
            <TableRow key={source.feed_id} className="hover:bg-muted/30">
              <TableCell className="font-medium">{source.feed_name}</TableCell>
              <TableCell>
                <span className={confidenceColor(source.source_confidence)}>
                  {source.source_confidence}
                </span>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(source.first_seen_by_feed)}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(source.last_seen_by_feed)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
