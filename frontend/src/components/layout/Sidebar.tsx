import { NavLink } from 'react-router-dom';
import { SignOut } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { useDashboard } from '@/hooks/useDashboard';
import { useAuth } from '@/contexts/AuthContext';
import { compactNumber } from '@/lib/dashboardFormat';
import { AppearanceSelector } from './AppearanceSelector';
import { NAV_ITEMS, type NavCount } from './navigation';

function getInitials(username: string): string {
  return username.slice(0, 2).toUpperCase();
}

interface SidebarProps {
  id?: string;
  className?: string;
  /** Called after a nav link is activated (the mobile drawer closes itself). */
  onNavigate?: () => void;
}

export function Sidebar({ id, className, onNavigate }: SidebarProps) {
  const { data } = useDashboard();
  const { user, logout } = useAuth();

  const counts: Record<NavCount, string> = {
    observables: data ? compactNumber(data.total_observables) : '—',
    feeds: data ? `${data.feeds_enabled}/${data.total_feeds}` : '—',
  };

  return (
    <aside id={id} className={cn('flex w-64 flex-col bg-card', className)}>
      <nav aria-label="Primary" className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.map(({ to, label, icon: ItemIcon, end, count }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-hover hover:text-foreground',
              )
            }
          >
            {({ isActive }) => (
              <>
                <ItemIcon size={18} weight={isActive ? 'fill' : 'regular'} aria-hidden="true" className="shrink-0" />
                <span className="flex-1 truncate">{label}</span>
                {count && (
                  <span
                    className={cn(
                      'rounded-full px-2 py-0.5 font-mono text-[11px] leading-4 tabular-nums',
                      isActive
                        ? 'bg-[color-mix(in_srgb,var(--on-primary)_16%,transparent)] text-primary-foreground'
                        : 'bg-surface3 text-muted-foreground',
                    )}
                  >
                    {counts[count]}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-4 border-t border-border px-4 py-4">
        <div className="space-y-2">
          <p aria-hidden="true" className="text-xs font-medium text-muted-foreground">
            Appearance
          </p>
          <AppearanceSelector />
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="flex items-center gap-2">
            <span aria-hidden="true" className="inline-block h-2 w-2 rounded-full bg-success" />
            API online
          </span>
          <span className="font-mono text-text3">v2.0.0</span>
        </div>

        {user && (
          <div className="flex items-center gap-2.5">
            <div
              aria-hidden="true"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[11px] font-semibold text-primary"
            >
              {getInitials(user.username)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">{user.username}</p>
              <p className="text-xs capitalize text-muted-foreground">{user.role}</p>
            </div>
            <button
              type="button"
              onClick={() => void logout()}
              className="shrink-0 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-hover hover:text-foreground"
              aria-label="Sign out"
              title="Sign out"
            >
              <SignOut size={16} aria-hidden="true" />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
