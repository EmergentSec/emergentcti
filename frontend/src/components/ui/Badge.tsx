import { type HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

const variants = {
  default: 'bg-primary text-primary-foreground',
  secondary: 'bg-secondary text-secondary-foreground',
  destructive: 'bg-destructive text-destructive-foreground',
  outline: 'border border-input text-foreground bg-transparent',
  success: 'bg-emerald-600 text-white',
  warning: 'bg-amber-600 text-white',
} as const;

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: keyof typeof variants;
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
