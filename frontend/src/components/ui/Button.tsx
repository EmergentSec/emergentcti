import { type ButtonHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';

const primary = 'bg-primary text-primary-foreground hover:bg-primary-hover';

const variants = {
  default: primary,
  /** Alias of `default`; `brand` is now the primary accent. */
  brand: primary,
  secondary: 'bg-surface3 text-foreground hover:bg-hover',
  outline: 'border border-borderStrong bg-card text-foreground hover:bg-hover',
  ghost: 'text-muted-foreground hover:bg-hover hover:text-foreground',
  destructive: 'bg-destructive text-destructive-foreground hover:opacity-90',
  /** Light button for use on the dark page-header band. */
  masthead:
    'bg-masthead-action text-masthead-action-foreground hover:bg-masthead-action-hover focus-visible:ring-offset-masthead',
} as const;

const sizes = {
  sm: 'h-8 px-3 text-xs',
  default: 'h-9 px-3.5 text-sm',
  lg: 'h-10 px-5 text-sm',
} as const;

export type ButtonVariant = keyof typeof variants;
export type ButtonSize = keyof typeof sizes;

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg font-medium transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background',
          'disabled:pointer-events-none disabled:opacity-50',
          variants[variant],
          sizes[size],
          className,
        )}
        disabled={disabled}
        {...props}
      />
    );
  },
);

Button.displayName = 'Button';
