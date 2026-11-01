import { type ReactNode } from 'react';
import { type Icon } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  icon?: Icon;
  /** Right-aligned actions; use `<Button variant="masthead">` on this band. */
  actions?: ReactNode;
  className?: string;
}

/** id of the page `h1`; the shell focuses it after drawer navigation. */
export const PAGE_HEADING_ID = 'page-heading';

/**
 * Full-bleed dark page-header band (dark in both themes). Below `sm` the
 * subtitle is visually hidden (kept for screen readers) so the title row fits.
 */
export function PageHeader({ title, subtitle, icon: HeaderIcon, actions, className }: PageHeaderProps) {
  return (
    <section className={cn('border-b border-masthead-border bg-masthead text-masthead-foreground', className)}>
      <div className="mx-auto flex max-w-[1320px] flex-wrap items-center gap-x-4 gap-y-3 px-4 py-5 sm:px-6">
        {HeaderIcon && (
          <div
            aria-hidden="true"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-masthead-border"
          >
            <HeaderIcon size={20} />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <h1
            id={PAGE_HEADING_ID}
            tabIndex={-1}
            className="truncate text-xl font-semibold leading-tight text-masthead-foreground focus:outline-none"
          >
            {title}
          </h1>
          {subtitle && <p className="sr-only text-sm text-masthead-muted sm:not-sr-only sm:mt-0.5">{subtitle}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </section>
  );
}
