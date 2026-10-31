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

/** Full-bleed dark page-header band (dark in both themes). */
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
          <h1 className="truncate text-xl font-semibold leading-tight text-masthead-foreground">{title}</h1>
          {subtitle && <p className="mt-0.5 text-sm text-masthead-muted">{subtitle}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </section>
  );
}
