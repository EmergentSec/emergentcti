import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/Table'
import { formatDate, formatRelativeTime } from '@/lib/utils'
import type { ObservableSource } from '@/types/observable'

interface DetailSourcesTabProps {
  sources: ObservableSource[]
}

function getConfColor(score: number): string {
  if (score >= 80) return 'var(--conf-critical)'
  if (score >= 60) return 'var(--conf-high)'
  if (score >= 40) return 'var(--conf-medium)'
  return 'var(--conf-low)'
}

export function DetailSourcesTab({ sources }: DetailSourcesTabProps) {
  if (sources.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Manually added — no feed sources
      </p>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Feed</TableHead>
          <TableHead className="w-32">Native conf</TableHead>
          <TableHead className="w-52">First seen</TableHead>
          <TableHead className="w-36">Last seen</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sources.map((source) => {
          const color = getConfColor(source.native_confidence)
          return (
            <TableRow key={source.feed_id}>
              <TableCell className="text-sm">{source.feed_name}</TableCell>
              <TableCell>
                <span
                  className="font-mono text-xs tabular-nums"
                  style={{ color }}
                >
                  {source.native_confidence}
                </span>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                {formatDate(source.first_seen_by_feed)}
              </TableCell>
              <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                {formatRelativeTime(source.last_seen_by_feed)}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
