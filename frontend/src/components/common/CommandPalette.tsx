import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGlobalKeyboardShortcut } from '@/hooks/useKeyboardShortcut';
import { searchObservables } from '@/api/search';
import { ObservableBadge } from '@/components/observables/ObservableBadge';
import { truncate } from '@/lib/utils';
import type { SearchHit } from '@/types/search';

interface CommandItem {
  id: string;
  label: string;
  path: string;
  type: 'navigation' | 'observable';
  observable?: SearchHit;
}

const STATIC_COMMANDS: CommandItem[] = [
  { id: 'nav-dashboard', label: 'Dashboard', path: '/', type: 'navigation' },
  { id: 'nav-observables', label: 'Observables', path: '/observables', type: 'navigation' },
  { id: 'nav-feeds', label: 'Feeds', path: '/feeds', type: 'navigation' },
  { id: 'nav-search', label: 'Search', path: '/search', type: 'navigation' },
  { id: 'nav-settings', label: 'Settings', path: '/settings', type: 'navigation' },
];

const PATH_HINTS: Record<string, string> = {
  'nav-dashboard': '/',
  'nav-observables': '/observables',
  'nav-feeds': '/feeds',
  'nav-search': '/search',
  'nav-settings': '/settings',
};

export function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<CommandItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();

  // Detect platform for shortcut display
  const isMac = typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0;

  // Cmd+K / Ctrl+K to toggle
  useGlobalKeyboardShortcut('k', () => {
    setIsOpen((prev) => !prev);
  }, isMac ? { meta: true } : { ctrl: true });

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      // Small delay to ensure the input is rendered
      requestAnimationFrame(() => {
        inputRef.current?.focus();
      });
    } else {
      setQuery('');
      setResults([]);
      setSelectedIndex(0);
      setIsSearching(false);
    }
  }, [isOpen]);

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setSelectedIndex(0);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const response = await searchObservables({ q: trimmed, size: 8 });
        const observableItems: CommandItem[] = response.hits.map((hit) => ({
          id: `obs-${hit.id}`,
          label: hit.value,
          path: `/observables/${hit.id}`,
          type: 'observable',
          observable: hit,
        }));
        setResults(observableItems);
        setSelectedIndex(0);
      } catch {
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query]);

  const displayItems = query.trim() ? results : STATIC_COMMANDS;

  const handleSelect = useCallback(
    (item: CommandItem) => {
      setIsOpen(false);
      navigate(item.path);
    },
    [navigate]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) =>
        prev < displayItems.length - 1 ? prev + 1 : 0
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) =>
        prev > 0 ? prev - 1 : displayItems.length - 1
      );
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (displayItems[selectedIndex]) {
        handleSelect(displayItems[selectedIndex]);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setIsOpen(false);
    }
  };

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      setIsOpen(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh] bg-black/50"
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div className="w-full max-w-lg rounded-lg bg-card shadow-2xl ring-1 ring-border overflow-hidden">
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-border px-4">
          <span className="text-muted-foreground shrink-0" aria-hidden="true">
            {'\u2315'}
          </span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Search... (${isMac ? 'Cmd' : 'Ctrl'}+K)`}
            className="flex-1 bg-transparent py-3 text-sm text-foreground placeholder:text-muted-foreground outline-none"
            aria-label="Command palette search"
            autoComplete="off"
            spellCheck={false}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="text-muted-foreground hover:text-foreground transition-colors text-xs"
              aria-label="Clear search"
            >
              {'\u2715'}
            </button>
          )}
        </div>

        {/* Results */}
        <div className="max-h-72 overflow-y-auto p-2" role="listbox">
          {!query.trim() && (
            <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Quick Navigation
            </div>
          )}

          {query.trim() && isSearching && (
            <div className="px-3 py-6 text-center text-sm text-muted-foreground">
              Searching...
            </div>
          )}

          {query.trim() && !isSearching && results.length === 0 && (
            <div className="px-3 py-6 text-center text-sm text-muted-foreground">
              No results found
            </div>
          )}

          {displayItems.map((item, index) => (
            <button
              key={item.id}
              role="option"
              aria-selected={index === selectedIndex}
              className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors ${
                index === selectedIndex
                  ? 'bg-accent text-accent-foreground'
                  : 'text-foreground hover:bg-accent/50'
              }`}
              onClick={() => handleSelect(item)}
              onMouseEnter={() => setSelectedIndex(index)}
            >
              {item.type === 'navigation' ? (
                <>
                  <span className="text-muted-foreground shrink-0">
                    {'\u25B8'}
                  </span>
                  <span className="flex-1">{item.label}</span>
                  <span className="text-xs text-muted-foreground font-mono">
                    {PATH_HINTS[item.id] || ''}
                  </span>
                </>
              ) : (
                <>
                  {item.observable && (
                    <ObservableBadge type={item.observable.type} />
                  )}
                  <span className="flex-1 font-mono text-sm truncate">
                    {truncate(item.label, 45)}
                  </span>
                  {item.observable && (
                    <span className="text-xs text-muted-foreground shrink-0">
                      Confidence: {item.observable.confidence}
                    </span>
                  )}
                </>
              )}
            </button>
          ))}
        </div>

        {/* Footer hint */}
        <div className="flex items-center gap-4 border-t border-border px-4 py-2 text-xs text-muted-foreground">
          <span>
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">{'\u2191'}</kbd>
            <kbd className="ml-0.5 rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">{'\u2193'}</kbd>
            {' '}navigate
          </span>
          <span>
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">Enter</kbd>
            {' '}select
          </span>
          <span>
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">Esc</kbd>
            {' '}close
          </span>
        </div>
      </div>
    </div>
  );
}
