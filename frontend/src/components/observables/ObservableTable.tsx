import { useNavigate } from 'react-router-dom';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { ObservableBadge } from './ObservableBadge';
import { ConfidenceMeter } from '@/components/common/ConfidenceMeter';
import { useToast } from '@/contexts/ToastContext';
import { cn, formatRelativeTime, truncate, TLP_COLORS } from '@/lib/utils';
import type { ObservableResponse } from '@/types/observable';

interface ObservableTableProps {
  observables: ObservableResponse[];
  isLoading?: boolean;
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onToggleSelectAll?: () => void;
}

export function ObservableTable({
  observables,
  isLoading,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
}: ObservableTableProps) {
  const navigate = useNavigate();
  const { addToast } = useToast();

  const handleCopyValue = async (
    e: React.MouseEvent,
    value: string
  ) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(value);
      addToast('Copied to clipboard', 'success');
    } catch {
      addToast('Failed to copy to clipboard', 'error');
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-16 animate-pulse rounded-lg bg-muted"
          />
        ))}
      </div>
    );
  }

  if (observables.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <span className="text-4xl mb-3">{'\u25C9'}</span>
        <p className="text-lg font-medium">No observables found</p>
        <p className="text-sm">
          Try adjusting your filters or add new observables
        </p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {onToggleSelect && (
            <TableHead className="w-10">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-input bg-background"
                checked={observables.length > 0 && observables.every((obs) => selectedIds?.has(obs.id))}
                onChange={() => onToggleSelectAll?.()}
              />
            </TableHead>
          )}
          <TableHead>Type</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Value</TableHead>
          <TableHead>TLP</TableHead>
          <TableHead>Confidence</TableHead>
          <TableHead>Source</TableHead>
          <TableHead>Category</TableHead>
          <TableHead>Tags</TableHead>
          <TableHead>Last Seen</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {observables.map((obs) => (
          <TableRow
            key={obs.id}
            className={cn("cursor-pointer", selectedIds?.has(obs.id) && "bg-primary/5")}
            onClick={() => navigate(`/observables/${obs.id}`)}
          >
            {onToggleSelect && (
              <TableCell onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-input bg-background"
                  checked={selectedIds?.has(obs.id) || false}
                  onChange={() => onToggleSelect(obs.id)}
                />
              </TableCell>
            )}
            <TableCell>
              <ObservableBadge type={obs.type} />
            </TableCell>
            <TableCell>
              {obs.is_active === false ? (
                <Badge
                  variant="outline"
                  className="bg-red-500/10 text-red-400 border-red-500/30 text-xs"
                >
                  Expired
                </Badge>
              ) : (
                <Badge
                  variant="outline"
                  className="bg-green-500/10 text-green-400 border-green-500/30 text-xs"
                >
                  Active
                </Badge>
              )}
            </TableCell>
            <TableCell>
              <div className="group/value flex items-center gap-1">
                <span className="font-mono text-sm" title={obs.value}>
                  {truncate(obs.value, 60)}
                </span>
                <button
                  onClick={(e) => handleCopyValue(e, obs.value)}
                  className="shrink-0 rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover/value:opacity-100"
                  aria-label={`Copy ${obs.value}`}
                  title="Copy to clipboard"
                >
                  <span className="text-xs">{'\u2398'}</span>
                </button>
              </div>
            </TableCell>
            <TableCell>
              <Badge
                variant="outline"
                className={TLP_COLORS[obs.tlp] || ''}
              >
                TLP:{obs.tlp.toUpperCase()}
              </Badge>
            </TableCell>
            <TableCell>
              <ConfidenceMeter value={obs.confidence_score} size="sm" />
            </TableCell>
            <TableCell>
              <span className="text-sm text-muted-foreground">
                {obs.sources.length > 0 ? obs.sources.map(s => s.name).join(', ') : '-'}
              </span>
            </TableCell>
            <TableCell>
              {obs.category ? (
                <Badge variant="secondary" className="text-xs">
                  {obs.category.charAt(0).toUpperCase() + obs.category.slice(1)}
                </Badge>
              ) : (
                <span className="text-sm text-muted-foreground">-</span>
              )}
            </TableCell>
            <TableCell>
              <div className="flex flex-wrap gap-1">
                {obs.tags.slice(0, 3).map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-xs">
                    {tag}
                  </Badge>
                ))}
                {obs.tags.length > 3 && (
                  <Badge variant="secondary" className="text-xs">
                    +{obs.tags.length - 3}
                  </Badge>
                )}
              </div>
            </TableCell>
            <TableCell>
              <span className="text-sm text-muted-foreground whitespace-nowrap">
                {obs.last_seen ? formatRelativeTime(obs.last_seen) : '-'}
              </span>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
