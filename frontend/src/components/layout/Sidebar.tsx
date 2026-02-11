import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import { canManageUsers } from '@/lib/permissions';
import { useSavedSearches } from '@/hooks/useSavedSearches';
import { EmergentLogo } from '@/components/common/EmergentLogo';
import type { SavedSearchFilters } from '@/types/saved_search';

interface NavItem {
  label: string;
  path: string;
  icon: string;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: '\u25A6' },
  { label: 'Observables', path: '/observables', icon: '\u25C9' },
  { label: 'Threat Actors', path: '/threat-actors', icon: '\u2620' },
  { label: 'Campaigns', path: '/campaigns', icon: '\u2691' },
  { label: 'ATT&CK', path: '/attack', icon: '\u2694' },
  { label: 'Feeds', path: '/feeds', icon: '\u21BB' },
  { label: 'Import', path: '/import', icon: '\u21A7' },
  { label: 'Alerts', path: '/alerts', icon: '\u26A0' },
  { label: 'Correlations', path: '/correlations', icon: '\u21C4' },
  { label: 'Graph', path: '/graph', icon: '\u2B53' },
  { label: 'Reports', path: '/reports', icon: '\u2637' },
  { label: 'Activity', path: '/activity', icon: '\u2630' },
  { label: 'Search', path: '/search', icon: '\u2315' },
  { label: 'Users', path: '/users', icon: '\u2302' },
  { label: 'Settings', path: '/settings', icon: '\u2699' },
];

function buildSearchParams(filters: SavedSearchFilters): string {
  const params = new URLSearchParams();
  if (filters.type) params.set('type', filters.type);
  if (filters.value) params.set('value', filters.value);
  if (filters.confidence_min != null)
    params.set('confidence_min', String(filters.confidence_min));
  if (filters.tlp) params.set('tlp', filters.tlp);
  if (filters.feed_id) params.set('feed_id', filters.feed_id);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export function Sidebar() {
  const { user } = useAuth();
  const { data: savedSearches } = useSavedSearches();
  const navigate = useNavigate();
  const [savedSearchesOpen, setSavedSearchesOpen] = useState(true);

  const topSearches = savedSearches?.slice(0, 5) ?? [];

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-64 flex-col border-r bg-card">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b px-6">
        <EmergentLogo size={32} className="shrink-0 text-foreground" />
        <div>
          <h1 className="text-lg font-bold leading-tight">EmergentCTI</h1>
          <p className="text-xs text-muted-foreground">Threat Intelligence</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 overflow-y-auto p-4">
        {navItems
          .filter((item) => item.path !== '/users' || canManageUsers(user))
          .map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )
            }
          >
            <span className="text-lg leading-none w-5 text-center">
              {item.icon}
            </span>
            {item.label}
          </NavLink>
        ))}

        {/* Saved Searches Section */}
        {topSearches.length > 0 && (
          <div className="mt-4 pt-4 border-t border-border">
            <button
              className="flex w-full items-center justify-between px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setSavedSearchesOpen(!savedSearchesOpen)}
            >
              <span>Saved Searches</span>
              <span className="text-[10px]">
                {savedSearchesOpen ? '\u25B4' : '\u25BE'}
              </span>
            </button>
            {savedSearchesOpen && (
              <div className="mt-1 space-y-0.5">
                {topSearches.map((search) => (
                  <button
                    key={search.id}
                    className={cn(
                      'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                      'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                    )}
                    onClick={() =>
                      navigate(
                        `/observables${buildSearchParams(search.filters)}`
                      )
                    }
                    title={search.name}
                  >
                    <span className="text-sm leading-none w-5 text-center">
                      {search.is_default ? '\u2605' : '\u2606'}
                    </span>
                    <span className="truncate">{search.name}</span>
                    {search.is_shared && (
                      <span className="ml-auto shrink-0 text-[10px] text-muted-foreground/60">
                        shared
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </nav>

      {/* Footer */}
      <div className="border-t p-4 space-y-3">
        <a
          href="/api/docs"
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
            'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
          )}
        >
          <span className="text-lg leading-none w-5 text-center">{'\u007B\u007D'}</span>
          API Docs
          <span className="ml-auto text-[10px] text-muted-foreground/60">{'\u2197'}</span>
        </a>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="inline-block h-2 w-2 rounded-full bg-green-500 animate-pulse-dot" />
          System Online
        </div>
      </div>
    </aside>
  );
}
