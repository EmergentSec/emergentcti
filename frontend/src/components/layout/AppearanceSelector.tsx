import { useRef, type KeyboardEvent } from 'react';
import { Desktop, Moon, Sun, type Icon } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/contexts/ThemeContext';
import { APPEARANCE_OPTIONS, type AppearancePreference } from '@/lib/appearance';

const OPTION_META: Record<AppearancePreference, { label: string; hint: string; icon: Icon }> = {
  system: { label: 'System', hint: 'Match your operating system', icon: Desktop },
  light: { label: 'Light', hint: 'Always use the light theme', icon: Sun },
  dark: { label: 'Dark', hint: 'Always use the dark theme', icon: Moon },
};

interface AppearanceSelectorProps {
  className?: string;
}

/**
 * System / Light / Dark segmented control (WAI-ARIA radio group).
 * Reflects the saved *preference*, so System stays checked while it resolves
 * to light or dark. Roving tabindex; arrows move and select; Home/End jump.
 */
export function AppearanceSelector({ className }: AppearanceSelectorProps) {
  const { preference, setPreference } = useTheme();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const options = APPEARANCE_OPTIONS;

  const select = (index: number) => {
    refs.current[index]?.focus();
    setPreference(options[index]);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = options.length - 1;
    let next: number | null = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = index === last ? 0 : index + 1;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = index === 0 ? last : index - 1;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = last;
    if (next === null) return;
    e.preventDefault();
    select(next);
  };

  return (
    <div
      role="radiogroup"
      aria-label="Appearance"
      className={cn('grid grid-cols-3 gap-0.5 rounded-lg border border-border bg-surface2 p-0.5', className)}
    >
      {options.map((opt, i) => {
        const { label, hint, icon: OptionIcon } = OPTION_META[opt];
        const checked = preference === opt;
        return (
          <button
            key={opt}
            ref={(el) => { refs.current[i] = el; }}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            title={hint}
            onClick={() => setPreference(opt)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cn(
              'flex h-8 min-w-0 items-center justify-center gap-1 rounded-md px-1.5 text-xs font-medium transition-colors',
              'focus-ring-inset',
              checked
                ? 'bg-card text-foreground shadow-card ring-1 ring-border'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <OptionIcon size={14} weight={checked ? 'fill' : 'regular'} aria-hidden="true" className="shrink-0" />
            <span className="truncate">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
