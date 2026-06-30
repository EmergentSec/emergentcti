import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { MagnifyingGlass, Sun, Moon, Plus } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '../ui/Button';

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  '/': { title: 'Dashboard', subtitle: 'Aggregation overview & feed health' },
  '/observables': { title: 'Observables', subtitle: 'Search and manage threat indicators' },
  '/feeds': { title: 'Feeds', subtitle: 'Manage intelligence feed sources' },
  '/settings': { title: 'Settings', subtitle: 'Platform configuration' },
};

interface HeaderProps {
  /** @deprecated — Header reads useAuth() directly; kept for back-compat with App.tsx */
  username?: string;
  /** @deprecated — Header reads useAuth() directly; kept for back-compat with App.tsx */
  onLogout?: () => void;
  className?: string;
}

export function Header({ className }: HeaderProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggle } = useTheme();
  const { isAdmin } = useAuth();
  const [search, setSearch] = useState('');

  const page = PAGE_META[location.pathname] ?? { title: 'EmergentCTI', subtitle: '' };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && search.trim()) {
      navigate(`/observables?q=${encodeURIComponent(search.trim())}`);
    }
  };

  return (
    <header
      className={cn(
        'sticky top-0 z-30 flex h-[60px] items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur',
        className,
      )}
    >
      {/* Left: title + subtitle */}
      <div className="flex flex-col justify-center">
        <h1 className="text-[16.5px] font-bold leading-tight text-foreground">{page.title}</h1>
        {page.subtitle && (
          <p className="text-xs text-muted-foreground">{page.subtitle}</p>
        )}
      </div>

      {/* Right: search + theme toggle + add */}
      <div className="flex items-center gap-3">
        {/* Search input */}
        <div className="relative flex items-center">
          <MagnifyingGlass
            size={15}
            className="absolute left-3 text-muted-foreground pointer-events-none"
          />
          <input
            type="text"
            className="h-8 w-56 rounded-md border border-border bg-surface pl-9 pr-12 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-brand"
            placeholder="Search observables, feeds, ha..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <span className="absolute right-2 rounded border border-border px-1 py-0.5 font-mono text-[10px] text-muted-foreground select-none">
            ⌘K
          </span>
        </div>

        {/* Theme toggle */}
        <button
          type="button"
          aria-label="Toggle theme"
          onClick={toggle}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-muted-foreground transition-colors hover:text-foreground"
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        {/* Add Observable — opens the create dialog on the Observables page (admin-only) */}
        {isAdmin && (
          <Button
            variant="brand"
            className="gap-1.5"
            onClick={() => navigate('/observables?create=1')}
          >
            <Plus size={14} weight="bold" />
            Add Observable
          </Button>
        )}
      </div>
    </header>
  );
}
