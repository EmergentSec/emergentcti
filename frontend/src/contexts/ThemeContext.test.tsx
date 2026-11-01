import { StrictMode } from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { ThemeProvider, useTheme } from './ThemeContext';
import { APPEARANCE_STORAGE_KEY, LEGACY_THEME_KEY } from '@/lib/appearance';
import { mockColorScheme, type MockColorScheme } from '@/test/matchMedia';

function Probe() {
  const { preference, resolvedTheme, setPreference } = useTheme();
  return (
    <div>
      <span data-testid="pref">{preference}</span>
      <span data-testid="resolved">{resolvedTheme}</span>
      <button onClick={() => setPreference('system')}>system</button>
      <button onClick={() => setPreference('light')}>light</button>
      <button onClick={() => setPreference('dark')}>dark</button>
    </div>
  );
}

function renderTheme() {
  return render(
    <StrictMode>
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    </StrictMode>,
  );
}

const html = () => document.documentElement;
const pref = () => screen.getByTestId('pref').textContent;
const resolved = () => screen.getByTestId('resolved').textContent;
const choose = (name: string) => screen.getByRole('button', { name }).click();

describe('ThemeContext appearance', () => {
  let os: MockColorScheme;

  beforeEach(() => {
    localStorage.clear();
    html().classList.remove('dark');
    html().style.colorScheme = '';
    delete html().dataset.appearance;
  });
  afterEach(() => {
    cleanup();
    os?.restore();
  });

  it('defaults a fresh browser to System and follows a dark OS', () => {
    os = mockColorScheme(true);
    renderTheme();
    expect(pref()).toBe('system');
    expect(resolved()).toBe('dark');
    expect(html().classList.contains('dark')).toBe(true);
    expect(html().style.colorScheme).toBe('dark');
    expect(html().dataset.appearance).toBe('system');
  });

  it('defaults a fresh browser to System and follows a light OS', () => {
    os = mockColorScheme(false);
    renderTheme();
    expect(pref()).toBe('system');
    expect(resolved()).toBe('light');
    expect(html().classList.contains('dark')).toBe(false);
  });

  it('does not persist anything until the user makes a choice', () => {
    os = mockColorScheme(false);
    renderTheme();
    expect(localStorage.getItem(APPEARANCE_STORAGE_KEY)).toBeNull();
  });

  it('reacts to OS appearance changes without reload while in System', () => {
    os = mockColorScheme(false);
    renderTheme();
    expect(resolved()).toBe('light');

    act(() => os.setDark(true));
    expect(resolved()).toBe('dark');
    expect(html().classList.contains('dark')).toBe(true);

    act(() => os.setDark(false));
    expect(resolved()).toBe('light');
    expect(html().classList.contains('dark')).toBe(false);
  });

  it('keeps explicit Light and Dark choices when the OS changes', () => {
    os = mockColorScheme(false);
    renderTheme();

    act(() => choose('dark'));
    act(() => os.setDark(false));
    expect(resolved()).toBe('dark');

    act(() => choose('light'));
    act(() => os.setDark(true));
    expect(resolved()).toBe('light');
    expect(html().classList.contains('dark')).toBe(false);
  });

  it('returns to the current OS value when switching back to System', () => {
    os = mockColorScheme(false);
    renderTheme();
    act(() => choose('light'));
    act(() => os.setDark(true));
    act(() => choose('system'));
    expect(resolved()).toBe('dark');
  });

  it.each([
    { choice: 'system' as const, osDark: true, expectedResolved: 'dark' },
    { choice: 'light' as const, osDark: true, expectedResolved: 'light' },
    { choice: 'dark' as const, osDark: false, expectedResolved: 'dark' },
  ])(
    'persists and reloads the $choice preference',
    ({ choice, osDark, expectedResolved }) => {
      os = mockColorScheme(osDark);
      const { unmount } = renderTheme();

      act(() => choose(choice));
      expect(localStorage.getItem(APPEARANCE_STORAGE_KEY)).toBe(choice);
      unmount();

      renderTheme();
      expect(pref()).toBe(choice);
      expect(resolved()).toBe(expectedResolved);
      expect(html().dataset.appearance).toBe(choice);
    },
  );

  it.each(['light', 'dark'] as const)(
    'migrates a legacy stored "%s" as an explicit choice',
    (legacy) => {
      os = mockColorScheme(legacy === 'light');
      localStorage.setItem(LEGACY_THEME_KEY, legacy);
      renderTheme();
      expect(pref()).toBe(legacy);
      expect(resolved()).toBe(legacy);
      expect(localStorage.getItem(APPEARANCE_STORAGE_KEY)).toBe(legacy);
      expect(localStorage.getItem(LEGACY_THEME_KEY)).toBeNull();
    },
  );

  it('prefers the new key and removes a stale legacy key', () => {
    os = mockColorScheme(false);
    localStorage.setItem(APPEARANCE_STORAGE_KEY, 'system');
    localStorage.setItem(LEGACY_THEME_KEY, 'dark');
    renderTheme();
    expect(pref()).toBe('system');
    expect(resolved()).toBe('light');
    expect(localStorage.getItem(LEGACY_THEME_KEY)).toBeNull();

    act(() => {
      localStorage.removeItem(APPEARANCE_STORAGE_KEY);
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: APPEARANCE_STORAGE_KEY,
          oldValue: 'system',
          newValue: null,
          storageArea: localStorage,
        }),
      );
    });
    expect(pref()).toBe('system');
  });

  it('ignores garbage stored values and falls back to System', () => {
    os = mockColorScheme(true);
    localStorage.setItem(APPEARANCE_STORAGE_KEY, 'purple');
    localStorage.setItem(LEGACY_THEME_KEY, 'neon');
    renderTheme();
    expect(pref()).toBe('system');
    expect(resolved()).toBe('dark');
  });

  it('updates when another tab changes the new storage key', () => {
    os = mockColorScheme(false);
    renderTheme();

    act(() => {
      localStorage.setItem(APPEARANCE_STORAGE_KEY, 'dark');
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: APPEARANCE_STORAGE_KEY,
          oldValue: null,
          newValue: 'dark',
          storageArea: localStorage,
        }),
      );
    });

    expect(pref()).toBe('dark');
    expect(resolved()).toBe('dark');
  });

  it('re-reads the preference when another tab clears storage', () => {
    os = mockColorScheme(true);
    localStorage.setItem(APPEARANCE_STORAGE_KEY, 'light');
    renderTheme();
    expect(pref()).toBe('light');

    act(() => {
      localStorage.clear();
      window.dispatchEvent(new StorageEvent('storage', { key: null, storageArea: localStorage }));
    });

    expect(pref()).toBe('system');
    expect(resolved()).toBe('dark');
  });

  it('uses legacy MediaQueryList listeners for live updates and cleanup', () => {
    os = mockColorScheme(false, { legacyListeners: true });
    const { unmount } = renderTheme();
    expect(os.listenerCount()).toBe(1);

    act(() => os.setDark(true));
    expect(resolved()).toBe('dark');

    unmount();
    expect(os.listenerCount()).toBe(0);
  });

  it('unsubscribes modern MediaQueryList listeners on unmount', () => {
    os = mockColorScheme(false);
    const { unmount } = renderTheme();
    expect(os.listenerCount()).toBe(1);
    unmount();
    expect(os.listenerCount()).toBe(0);
  });
});
