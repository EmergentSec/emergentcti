// frontend/src/components/ui/Tabs.tsx
import { useRef, type KeyboardEvent } from 'react';
import { cn } from '@/lib/utils';

export interface TabItem { key: string; label: string; }
export interface TabsProps {
  tabs: TabItem[];
  active: string;
  onChange: (key: string) => void;
  className?: string;
}

/**
 * Underline tabs. Keyboard: roving tabindex (only the selected tab is in the
 * Tab order); Arrow Left/Right move focus and select, Home/End jump to ends.
 */
export function Tabs({ tabs, active, onChange, className }: TabsProps) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const activeIndex = Math.max(0, tabs.findIndex((t) => t.key === active));

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let next: number | null = null;
    if (e.key === 'ArrowRight') next = (index + 1) % tabs.length;
    else if (e.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = tabs.length - 1;
    if (next === null) return;
    e.preventDefault();
    refs.current[next]?.focus();
    if (tabs[next].key !== active) onChange(tabs[next].key);
  };

  return (
    <div role="tablist" className={cn('flex gap-1 overflow-x-auto border-b border-border', className)}>
      {tabs.map((t, i) => {
        const selected = t.key === active;
        return (
          <button
            key={t.key}
            ref={(el) => { refs.current[i] = el; }}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={i === activeIndex ? 0 : -1}
            onClick={() => { if (!selected) onChange(t.key); }}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cn(
              'focus-ring-inset -mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition-colors',
              selected
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:border-borderStrong hover:text-foreground',
            )}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
