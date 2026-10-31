import { useEffect, useRef, useState, type RefObject } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { List, MagnifyingGlass, X } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { EmergentLogo } from '../common/EmergentLogo';

function isApplePlatform(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /Mac|iPhone|iPad|iPod/i.test(navigator.platform || navigator.userAgent);
}

interface HeaderProps {
  /** Toggles the sidebar (drawer below `lg`, collapse at `lg`+). */
  onMenuClick?: () => void;
  /** Whether the navigation the menu button controls is currently shown. */
  menuExpanded?: boolean;
  /** id of the element the menu button controls. */
  menuControls?: string;
  menuButtonRef?: RefObject<HTMLButtonElement>;
  /** @deprecated — the shell reads useAuth() directly; kept for back-compat with App.tsx */
  username?: string;
  /** @deprecated — the shell reads useAuth() directly; kept for back-compat with App.tsx */
  onLogout?: () => void;
  className?: string;
}

/** Full-width top bar: menu button, wordmark, global observable search (⌘K / Ctrl+K). */
export function Header({ onMenuClick, menuExpanded, menuControls, menuButtonRef, className }: HeaderProps) {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  // Below `md` the search field collapses to an icon button.
  const [searchOpen, setSearchOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const searchButtonRef = useRef<HTMLButtonElement>(null);
  const shortcut = isApplePlatform() ? '⌘K' : 'Ctrl K';

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && !e.altKey && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen(true);
        // Focus after the collapsed field (if any) has been revealed.
        requestAnimationFrame(() => inputRef.current?.focus());
        inputRef.current?.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const openSearch = () => {
    setSearchOpen(true);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const closeSearch = () => {
    setSearchOpen(false);
    searchButtonRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && search.trim()) {
      navigate(`/observables?q=${encodeURIComponent(search.trim())}`);
      setSearchOpen(false);
    } else if (e.key === 'Escape') {
      if (searchOpen) closeSearch();
      else inputRef.current?.blur();
    }
  };

  return (
    <header
      className={cn(
        'sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-card px-3 sm:px-4',
        className,
      )}
    >
      <button
        ref={menuButtonRef}
        type="button"
        aria-label="Toggle navigation"
        aria-expanded={menuExpanded}
        aria-controls={menuControls}
        onClick={onMenuClick}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-hover hover:text-foreground"
      >
        <List size={20} aria-hidden="true" />
      </button>

      <Link to="/" className="flex min-w-0 items-center gap-2.5 rounded-md">
        <EmergentLogo size={26} className="shrink-0 text-foreground" />
        <span className="truncate text-[15px] font-semibold tracking-tight text-foreground">EmergentCTI</span>
      </Link>

      <div className="ml-auto flex items-center">
        {/* Narrow screens: icon that expands the search field over the bar */}
        <button
          ref={searchButtonRef}
          type="button"
          aria-label="Search"
          onClick={openSearch}
          className={cn(
            'flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-hover hover:text-foreground md:hidden',
            searchOpen && 'invisible',
          )}
        >
          <MagnifyingGlass size={18} aria-hidden="true" />
        </button>

        <div
          role="search"
          className={cn(
            'items-center gap-2',
            searchOpen ? 'absolute inset-0 z-10 flex bg-card px-3' : 'hidden',
            'md:static md:flex md:bg-transparent md:p-0',
          )}
        >
          <div className="relative flex flex-1 items-center">
            <MagnifyingGlass
              size={15}
              aria-hidden="true"
              className="pointer-events-none absolute left-3 text-text3"
            />
            <input
              ref={inputRef}
              type="search"
              aria-label="Search observables"
              aria-keyshortcuts="Meta+K Control+K"
              className="h-9 w-full rounded-lg border border-borderStrong bg-surface2 pl-9 pr-16 text-sm text-foreground placeholder:text-text3 focus-visible:border-primary focus-visible:bg-card focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary md:w-72 lg:w-80"
              placeholder="Search observables, feeds, hashes…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <kbd
              aria-hidden="true"
              className="pointer-events-none absolute right-2 hidden select-none rounded border border-border bg-card px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:block"
            >
              {shortcut}
            </kbd>
          </div>
          {searchOpen && (
            <button
              type="button"
              aria-label="Close search"
              onClick={closeSearch}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-hover hover:text-foreground md:hidden"
            >
              <X size={18} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
