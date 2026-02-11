import { cn } from '@/lib/utils';

interface ConfidenceMeterProps {
  value: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

function getConfidenceColor(value: number): string {
  if (value >= 80) return 'bg-green-500';
  if (value >= 60) return 'bg-yellow-500';
  if (value >= 40) return 'bg-orange-500';
  return 'bg-red-500';
}

function getConfidenceTextColor(value: number): string {
  if (value >= 80) return 'text-green-400';
  if (value >= 60) return 'text-yellow-400';
  if (value >= 40) return 'text-orange-400';
  return 'text-red-400';
}

const sizeClasses: Record<string, { bar: string; text: string }> = {
  sm: { bar: 'h-1.5 w-16', text: 'text-xs' },
  md: { bar: 'h-2 w-24', text: 'text-sm' },
  lg: { bar: 'h-3 w-32', text: 'text-base' },
};

export function ConfidenceMeter({
  value,
  size = 'md',
  showLabel = true,
  className,
}: ConfidenceMeterProps) {
  const clamped = Math.max(0, Math.min(100, value ?? 0));

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div
        className={cn(
          'overflow-hidden rounded-full bg-muted',
          sizeClasses[size].bar
        )}
      >
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            getConfidenceColor(clamped)
          )}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && (
        <span
          className={cn(
            'font-medium tabular-nums',
            sizeClasses[size].text,
            getConfidenceTextColor(clamped)
          )}
        >
          {clamped}%
        </span>
      )}
    </div>
  );
}
