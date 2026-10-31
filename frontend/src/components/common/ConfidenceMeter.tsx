import { cn } from '@/lib/utils';

interface ConfidenceMeterProps {
  score: number;
  showBar?: boolean;
  className?: string;
}

function getColor(score: number) {
  if (score >= 80) return { text: 'text-conf-critical', bg: 'bg-conf-critical' };
  if (score >= 60) return { text: 'text-conf-high', bg: 'bg-conf-high' };
  if (score >= 40) return { text: 'text-conf-medium', bg: 'bg-conf-medium' };
  return { text: 'text-conf-low', bg: 'bg-conf-low' };
}

function getLabel(score: number) {
  if (score >= 80) return 'Critical';
  if (score >= 60) return 'High';
  if (score >= 40) return 'Medium';
  return 'Low';
}

export function ConfidenceMeter({ score, showBar = true, className }: ConfidenceMeterProps) {
  const color = getColor(score);
  const clamped = Math.max(0, Math.min(100, score));

  return (
    <div className={cn('flex items-center gap-2', className)}>
      {showBar && (
        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface3">
          <div
            className={cn('h-full rounded-full transition-all', color.bg)}
            style={{ width: `${clamped}%` }}
          />
        </div>
      )}
      <span className={cn('text-sm font-medium tabular-nums', color.text)}>
        {clamped}
      </span>
      <span className={cn('text-xs', color.text)}>
        {getLabel(clamped)}
      </span>
    </div>
  );
}
