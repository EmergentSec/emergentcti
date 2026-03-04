import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { EmergentLogo } from '../common/EmergentLogo';

const navItems = [
  {
    to: '/',
    label: 'Dashboard',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="2" width="7" height="8" rx="1" />
        <rect x="11" y="2" width="7" height="5" rx="1" />
        <rect x="2" y="12" width="7" height="6" rx="1" />
        <rect x="11" y="9" width="7" height="9" rx="1" />
      </svg>
    ),
  },
  {
    to: '/observables',
    label: 'Observables',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="10" cy="10" r="7" />
        <circle cx="10" cy="10" r="3" />
        <line x1="10" y1="3" x2="10" y2="1" />
        <line x1="10" y1="19" x2="10" y2="17" />
        <line x1="3" y1="10" x2="1" y2="10" />
        <line x1="19" y1="10" x2="17" y2="10" />
      </svg>
    ),
  },
  {
    to: '/feeds',
    label: 'Feeds',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 3v14h14" />
        <path d="M7 13l3-3 3 2 4-5" />
      </svg>
    ),
  },
  {
    to: '/settings',
    label: 'Settings',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="10" cy="10" r="2.5" />
        <path d="M10 1.5v2M10 16.5v2M3.3 3.3l1.4 1.4M15.3 15.3l1.4 1.4M1.5 10h2M16.5 10h2M3.3 16.7l1.4-1.4M15.3 4.7l1.4-1.4" />
      </svg>
    ),
  },
];

export function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-border bg-card">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5">
        <EmergentLogo size={32} />
        <span className="text-lg font-bold text-foreground tracking-tight">EmergentCTI</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground',
              )
            }
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-border px-5 py-3">
        <p className="text-xs text-muted-foreground">v2.0.0</p>
      </div>
    </aside>
  );
}
