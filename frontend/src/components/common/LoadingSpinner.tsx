import { cn } from '@/lib/utils';

const sizes = {
  sm: 'h-4 w-4 border-2',
  default: 'h-8 w-8 border-2',
  lg: 'h-12 w-12 border-3',
} as const;

interface LoadingSpinnerProps {
  size?: keyof typeof sizes;
  className?: string;
}

export function LoadingSpinner({ size = 'default', className }: LoadingSpinnerProps) {
  return (
    <div
      className={cn(
        'animate-spin rounded-full border-muted border-t-primary',
        sizes[size],
        className,
      )}
      role="status"
      aria-label="Loading"
    />
  );
}
