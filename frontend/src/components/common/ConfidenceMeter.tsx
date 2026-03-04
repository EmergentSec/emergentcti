import { cn } from '@/lib/utils';

interface ConfidenceMeterProps {
  score: number;
  showBar?: boolean;
  className?: string;
}

function getColor(score: number) {
  if (score >= 80) return { text: 'text-red-400', bg: 'bg-red-500', bar: 'bg-red-500/20' };
  if (score >= 60) return { text: 'text-orange-400', bg: 'bg-orange-500', bar: 'bg-orange-500/20' };
  if (score >= 40) return { text: 'text-yellow-400', bg: 'bg-yellow-500', bar: 'bg-yellow-500/20' };
  return { text: 'text-gray-400', bg: 'bg-gray-500', bar: 'bg-gray-500/20' };
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
        <div className={cn('h-2 w-16 rounded-full', color.bar)}>
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
