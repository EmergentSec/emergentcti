// Executes the real inline boot script from index.html so the pre-paint theme
// can never drift from the React ThemeProvider's resolution rules.
/// <reference types="vite/client" />
import indexHtml from '../../index.html?raw';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { APPEARANCE_STORAGE_KEY, LEGACY_THEME_KEY, readPreference, resolveTheme } from './appearance';
import { mockColorScheme, type MockColorScheme } from '@/test/matchMedia';

const bootSource = (() => {
  const m = indexHtml.match(/<script id="appearance-boot">([\s\S]*?)<\/script>/);
  if (!m) throw new Error('appearance-boot script missing from index.html');
  return m[1];
})();

function runBoot() {
  new Function(bootSource)();
}

const html = () => document.documentElement;

describe('index.html appearance boot script', () => {
  let os: MockColorScheme;
  beforeEach(() => {
    localStorage.clear();
    html().classList.remove('dark');
    html().style.colorScheme = '';
  });
  afterEach(() => os?.restore());

  const cases: Array<{ name: string; stored?: string; legacy?: string; osDark: boolean }> = [
    { name: 'fresh, OS dark', osDark: true },
    { name: 'fresh, OS light', osDark: false },
    { name: 'system, OS dark', stored: 'system', osDark: true },
    { name: 'explicit light, OS dark', stored: 'light', osDark: true },
    { name: 'explicit dark, OS light', stored: 'dark', osDark: false },
    { name: 'legacy light, OS dark', legacy: 'light', osDark: true },
    { name: 'legacy dark, OS light', legacy: 'dark', osDark: false },
    { name: 'garbage values, OS dark', stored: 'x', legacy: 'y', osDark: true },
  ];

  it.each(cases)('matches the app resolution: $name', ({ stored, legacy, osDark }) => {
    os = mockColorScheme(osDark);
    const seed = () => {
      localStorage.clear();
      if (stored) localStorage.setItem(APPEARANCE_STORAGE_KEY, stored);
      if (legacy) localStorage.setItem(LEGACY_THEME_KEY, legacy);
    };

    seed();
    runBoot();
    const bootDark = html().classList.contains('dark');
    const bootStored = localStorage.getItem(APPEARANCE_STORAGE_KEY);

    seed();
    const expected = resolveTheme(readPreference(), osDark);
    expect(bootDark).toBe(expected === 'dark');
    expect(html().style.colorScheme).toBe(expected);
    // Both paths perform the same migration side effect.
    expect(bootStored).toBe(localStorage.getItem(APPEARANCE_STORAGE_KEY));
  });

  it('survives storage that throws', () => {
    os = mockColorScheme(true);
    const original = globalThis.localStorage;
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      get() {
        throw new Error('denied');
      },
    });
    try {
      expect(() => runBoot()).not.toThrow();
      expect(html().classList.contains('dark')).toBe(true);
      expect(readPreference()).toBe('system');
    } finally {
      Object.defineProperty(globalThis, 'localStorage', { configurable: true, writable: true, value: original });
    }
  });
});
