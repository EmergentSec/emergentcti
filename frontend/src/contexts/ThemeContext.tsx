import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  APPEARANCE_STORAGE_KEY,
  DARK_QUERY,
  applyTheme,
  readPreference,
  resolveTheme,
  systemPrefersDark,
  writePreference,
  type AppearancePreference,
  type ResolvedTheme,
} from '@/lib/appearance';

interface ThemeValue {
  /** What the user selected; persisted. */
  preference: AppearancePreference;
  /** What is actually applied right now. */
  resolvedTheme: ResolvedTheme;
  setPreference: (pref: AppearancePreference) => void;
}

const ThemeContext = createContext<ThemeValue | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<AppearancePreference>(readPreference);
  const [osDark, setOsDark] = useState<boolean>(systemPrefersDark);

  // Follow OS appearance changes live. Always subscribed so switching back to
  // System picks up the current OS value without a stale snapshot.
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const mql = window.matchMedia(DARK_QUERY);
    const onChange = (e: MediaQueryListEvent) => setOsDark(e.matches);
    setOsDark(mql.matches);
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, []);

  // Keep other tabs in sync when the preference changes elsewhere.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === APPEARANCE_STORAGE_KEY) setPreferenceState(readPreference());
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const resolvedTheme = resolveTheme(preference, osDark);

  useEffect(() => {
    applyTheme(resolvedTheme, preference);
  }, [resolvedTheme, preference]);

  const setPreference = useCallback((pref: AppearancePreference) => {
    writePreference(pref);
    setPreferenceState(pref);
  }, []);

  const value = useMemo(
    () => ({ preference, resolvedTheme, setPreference }),
    [preference, resolvedTheme, setPreference],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
