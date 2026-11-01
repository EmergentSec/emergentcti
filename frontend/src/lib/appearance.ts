// Appearance preference model.
//
// `preference` is what the user chose (system | light | dark) and is what we
// persist. `resolved` is the concrete theme applied to the document. Keep this
// logic in sync with the inline boot script in index.html (covered by
// appearance.test.ts, which executes that script).

export type AppearancePreference = 'system' | 'light' | 'dark';
export type ResolvedTheme = 'light' | 'dark';

export const APPEARANCE_STORAGE_KEY = 'emergentcti.appearance';
/** Pre-refresh key written by the old binary toggle ('light' | 'dark'). */
export const LEGACY_THEME_KEY = 'theme';
export const DARK_QUERY = '(prefers-color-scheme: dark)';

export const APPEARANCE_OPTIONS: readonly AppearancePreference[] = ['system', 'light', 'dark'];

function isPreference(v: unknown): v is AppearancePreference {
  return v === 'system' || v === 'light' || v === 'dark';
}

function safeStorage(): Storage | null {
  try {
    return typeof localStorage !== 'undefined' ? localStorage : null;
  } catch {
    return null; // storage disabled (privacy mode, sandboxed iframe)
  }
}

/**
 * Read the stored preference, migrating the legacy `theme` key once.
 * A fresh browser (nothing stored) gets 'system'.
 */
export function readPreference(): AppearancePreference {
  const store = safeStorage();
  if (!store) return 'system';

  try {
    const current = store.getItem(APPEARANCE_STORAGE_KEY);
    if (isPreference(current)) {
      try {
        store.removeItem(LEGACY_THEME_KEY);
      } catch {
        /* stale legacy cleanup is best effort */
      }
      return current;
    }
  } catch {
    return 'system';
  }

  let legacy: string | null;
  try {
    legacy = store.getItem(LEGACY_THEME_KEY);
  } catch {
    return 'system';
  }

  if (legacy === 'light' || legacy === 'dark') {
    try {
      store.setItem(APPEARANCE_STORAGE_KEY, legacy);
      store.removeItem(LEGACY_THEME_KEY);
    } catch {
      /* migration writes are best effort; keep the valid legacy preference */
    }
    return legacy;
  }

  return 'system';
}

export function writePreference(pref: AppearancePreference): void {
  const store = safeStorage();
  if (!store) return;
  try {
    store.setItem(APPEARANCE_STORAGE_KEY, pref);
  } catch {
    /* ignore */
  }
}

export function systemPrefersDark(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia(DARK_QUERY).matches
    : false;
}

export function resolveTheme(pref: AppearancePreference, osDark: boolean): ResolvedTheme {
  if (pref === 'system') return osDark ? 'dark' : 'light';
  return pref;
}

/** Apply the resolved theme to <html>: `.dark` class + native color-scheme. */
export function applyTheme(resolved: ResolvedTheme, pref: AppearancePreference): void {
  const root = document.documentElement;
  root.classList.toggle('dark', resolved === 'dark');
  root.style.colorScheme = resolved;
  root.dataset.appearance = pref;
}
