import { Badge } from '@/components/ui/badge';
import {
  cn,
  OBSERVABLE_TYPE_COLORS,
  OBSERVABLE_TYPE_LABELS,
} from '@/lib/utils';
import type { ObservableType } from '@/types/observable';

interface ObservableBadgeProps {
  type: ObservableType;
  className?: string;
}

export function ObservableBadge({ type, className }: ObservableBadgeProps) {
  const colorClass = OBSERVABLE_TYPE_COLORS[type] || OBSERVABLE_TYPE_COLORS['command-line'];
  const label = OBSERVABLE_TYPE_LABELS[type] || type;

  return (
    <Badge
      variant="outline"
      className={cn('font-mono text-xs', colorClass, className)}
    >
      {label}
    </Badge>
  );
}
