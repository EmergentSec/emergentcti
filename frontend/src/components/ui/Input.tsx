import { type InputHTMLAttributes, forwardRef, useId } from 'react';
import { cn } from '@/lib/utils';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

/** Shared control styling for text inputs and selects. */
export const controlClass = cn(
  'flex h-9 w-full rounded-lg border border-borderStrong bg-card px-3 text-sm text-foreground',
  'placeholder:text-text3',
  'transition-colors focus-visible:outline-none focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary',
  'disabled:cursor-not-allowed disabled:opacity-50',
);

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, 'aria-describedby': describedBy, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');
    const errorId = `${useId()}-error`;

    return (
      <div className="space-y-1.5">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-foreground">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={[describedBy, error && errorId].filter(Boolean).join(' ') || undefined}
          className={cn(
            controlClass,
            error && 'border-destructive focus-visible:border-destructive focus-visible:ring-destructive',
            className,
          )}
          {...props}
        />
        {error && (
          <p id={errorId} className="text-xs text-destructive">
            {error}
          </p>
        )}
      </div>
    );
  },
);

Input.displayName = 'Input';
