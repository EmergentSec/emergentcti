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

const html = () => document.documentElement;
const pref = () => screen.getByTestId('pref').textContent;
const resolved = () => screen.getByTestId('resolved').textContent;
const choose = (name: string) => screen.getByRole('button', { name }).click();

describe('ThemeContext appearance', () => {
  let os: MockColorScheme;

  beforeEach(() => {
    localStorage.clear();
    html().classList.remove('dark');
  });
  afterEach(() => {
    cleanup();
    os?.restore();
  });

  it('defaults a fresh browser to System and follows a dark OS', () => {
    os = mockColorScheme(true);
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(pref()).toBe('system');
    expect(resolved()).toBe('dark');
    expect(html().classList.contains('dark')).toBe(true);
    expect(html().style.colorScheme).toBe('dark');
  });

  it('defaults a fresh browser to System and follows a light OS', () => {
    os = mockColorScheme(false);
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(pref()).toBe('system');
    expect(resolved()).toBe('light');
    expect(html().classList.contains('dark')).toBe(false);
  });

  it('does not persist anything until the user makes a choice', () => {
    os = mockColorScheme(false);
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(localStorage.getItem(APPEARANCE_STORAGE_KEY)).toBeNull();
  });

  it('reacts to OS appearance changes without reload while in System', () => {
    os = mockColorScheme(false);
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(resolved()).toBe('light');

    act(() => os.setDark(true));
    expect(resolved()).toBe('dark');
    expect(html().classList.contains('dark')).toBe(true);

    act(() => os.setDark(false));
    expect(resolved()).toBe('light');
    expect(html().classList.contains('dark')).toBe(false);
  });

  it('keeps explicit Light / Dark when the OS changes', () => {
    os = mockColorScheme(false);
    render(<ThemeProvider><Probe /></ThemeProvider>);

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
    render(<ThemeProvider><Probe /></ThemeProvider>);
    act(() => choose('light'));
    act(() => os.setDark(true)); // OS changes while explicitly light
    act(() => choose('system'));
    expect(resolved()).toBe('dark');
  });

  it('persists each explicit choice, including System', () => {
    os = mockColorScheme(false);
    const { unmount } = render(<ThemeProvider><Probe /></ThemeProvider>);
    act(() => choose('dark'));
    expect(localStorage.getItem(APPEARANCE_STORAGE_KEY)).toBe('dark');
    unmount();

    // "Reload"
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(pref()).toBe('dark');
    expect(resolved()).toBe('dark');

    act(() => choose('system'));
    expect(localStorage.getItem(APPEARANCE_STORAGE_KEY)).toBe('system');
  });

  it.each(['light', 'dark'] as const)(
    'migrates a legacy stored "%s" as an explicit choice',
    (legacy) => {
      os = mockColorScheme(legacy === 'light'); // OS deliberately disagrees
      localStorage.setItem(LEGACY_THEME_KEY, legacy);
      render(<ThemeProvider><Probe /></ThemeProvider>);
      expect(pref()).toBe(legacy);
      expect(resolved()).toBe(legacy);
      expect(localStorage.getItem(APPEARANCE_STORAGE_KEY)).toBe(legacy);
      expect(localStorage.getItem(LEGACY_THEME_KEY)).toBeNull();
    },
  );

  it('prefers the new key over a stale legacy key', () => {
    os = mockColorScheme(false);
    localStorage.setItem(APPEARANCE_STORAGE_KEY, 'system');
    localStorage.setItem(LEGACY_THEME_KEY, 'dark');
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(pref()).toBe('system');
    expect(resolved()).toBe('light');
  });

  it('ignores garbage stored values and falls back to System', () => {
    os = mockColorScheme(true);
    localStorage.setItem(APPEARANCE_STORAGE_KEY, 'purple');
    localStorage.setItem(LEGACY_THEME_KEY, 'neon');
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(pref()).toBe('system');
    expect(resolved()).toBe('dark');
  });

  it('unsubscribes from OS changes on unmount', () => {
    os = mockColorScheme(false);
    const { unmount } = render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(os.listenerCount()).toBe(1);
    unmount();
    expect(os.listenerCount()).toBe(0);
  });
});
