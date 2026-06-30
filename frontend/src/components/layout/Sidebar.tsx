import { NavLink } from 'react-router-dom';
import { SquaresFour, CrosshairSimple, Rss, GearSix, SignOut } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { EmergentLogo } from '../common/EmergentLogo';
import { useDashboard } from '@/hooks/useDashboard';
import { useAuth } from '@/contexts/AuthContext';
import { compactNumber } from '@/lib/dashboardFormat';

function getInitials(username: string): string {
  return username.slice(0, 2).toUpperCase();
}

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'flex items-center justify-between rounded-md px-3 py-2 text-sm transition-colors',
    isActive
      ? 'text-brand font-bold'
      : 'font-medium text-muted-foreground hover:text-foreground hover:bg-hover',
  );

const navLinkStyle = ({ isActive }: { isActive: boolean }): React.CSSProperties =>
  isActive ? { background: 'color-mix(in srgb, var(--brand) 13%, transparent)' } : {};

export function Sidebar() {
  const { data } = useDashboard();
  const { user, logout } = useAuth();

  const observablesCount = data ? compactNumber(data.total_observables) : '—';
  const feedsCount = data ? `${data.feeds_enabled}/${data.total_feeds}` : '—';

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-[236px] flex-col border-r border-border bg-card">
      {/* Logo + wordmark */}
      <div className="flex items-center gap-3 px-5 py-5">
        <EmergentLogo size={28} />
        <div className="flex flex-col">
          <span className="text-[15px] font-bold leading-tight text-foreground">EmergentCTI</span>
          <span className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
            Threat Intelligence
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 px-3 py-2">
        <NavLink to="/" end className={navLinkClass} style={navLinkStyle}>
          <span className="flex items-center gap-3">
            <SquaresFour size={18} />
            Dashboard
          </span>
        </NavLink>

        <NavLink to="/observables" className={navLinkClass} style={navLinkStyle}>
          <span className="flex items-center gap-3">
            <CrosshairSimple size={18} />
            Observables
          </span>
          <span className="font-mono text-xs">{observablesCount}</span>
        </NavLink>

        <NavLink to="/feeds" className={navLinkClass} style={navLinkStyle}>
          <span className="flex items-center gap-3">
            <Rss size={18} />
            Feeds
          </span>
          <span className="font-mono text-xs">{feedsCount}</span>
        </NavLink>

        <NavLink to="/settings" className={navLinkClass} style={navLinkStyle}>
          <span className="flex items-center gap-3">
            <GearSix size={18} />
            Settings
          </span>
        </NavLink>
      </nav>

      {/* Footer */}
      <div className="border-t border-border px-4 py-3 space-y-3">
        {/* API status row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
            <span className="text-xs text-muted-foreground">API online</span>
          </div>
          <span className="font-mono text-xs text-muted-foreground">v2.0.0</span>
        </div>

        {/* User row */}
        {user && (
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand text-[11px] font-bold text-brand-foreground">
              {getInitials(user.username)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">{user.username}</p>
              <p className="text-xs capitalize text-muted-foreground">{user.role}</p>
            </div>
            <button
              onClick={() => void logout()}
              className="shrink-0 text-muted-foreground transition-colors hover:text-foreground"
              aria-label="Sign out"
            >
              <SignOut size={16} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
