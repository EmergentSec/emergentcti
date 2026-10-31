// Executes the real inline boot script from index.html so the pre-paint theme
// can never drift from the React ThemeProvider's resolution rules.
/// <reference types="vite/client" />
import indexHtml from '../../index.html?raw';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  APPEARANCE_STORAGE_KEY,
  LEGACY_THEME_KEY,
  applyTheme,
  readPreference,
  resolveTheme,
} from './appearance';
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

type StorageFailure = 'getItem' | 'setItem' | 'removeItem';
type StorageEntries = Record<string, string>;

function withStorage<T>(
  seed: StorageEntries,
  failure: StorageFailure | undefined,
  run: (entries: Map<string, string>) => T,
): T {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  const entries = new Map(Object.entries(seed));
  const storage: Storage = {
    get length() {
      return entries.size;
    },
    clear() {
      entries.clear();
    },
    getItem(key) {
      if (failure === 'getItem') throw new Error('getItem denied');
      return entries.get(key) ?? null;
    },
    key(index) {
      return [...entries.keys()][index] ?? null;
    },
    removeItem(key) {
      if (failure === 'removeItem') throw new Error('removeItem denied');
      entries.delete(key);
    },
    setItem(key, value) {
      if (failure === 'setItem') throw new Error('setItem denied');
      entries.set(key, String(value));
    },
  };

  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: storage,
  });
  try {
    return run(entries);
  } finally {
    if (descriptor) Object.defineProperty(globalThis, 'localStorage', descriptor);
    else delete (globalThis as { localStorage?: Storage }).localStorage;
  }
}

function resetDocumentAppearance() {
  html().classList.remove('dark');
  html().style.colorScheme = '';
  delete html().dataset.appearance;
}

function storageEntries(entries: Map<string, string>) {
  return Object.fromEntries(entries.entries());
}

function evaluateAppearance(
  mode: 'boot' | 'app',
  seed: StorageEntries,
  failure?: StorageFailure,
) {
  resetDocumentAppearance();
  return withStorage(seed, failure, (entries) => {
    if (mode === 'boot') {
      runBoot();
    } else {
      const preference = readPreference();
      const resolved = resolveTheme(
        preference,
        window.matchMedia('(prefers-color-scheme: dark)').matches,
      );
      applyTheme(resolved, preference);
    }

    return {
      preference: html().dataset.appearance,
      resolved: html().style.colorScheme,
      dark: html().classList.contains('dark'),
      storage: storageEntries(entries),
    };
  });
}

describe('index.html appearance boot script', () => {
  let os: MockColorScheme;
  beforeEach(() => {
    localStorage.clear();
    resetDocumentAppearance();
  });
  afterEach(() => os?.restore());

  const cases: Array<{
    name: string;
    seed?: StorageEntries;
    failure?: StorageFailure;
    osDark: boolean;
    expectedPreference: 'system' | 'light' | 'dark';
    expectedStorage?: StorageEntries;
  }> = [
    { name: 'fresh, OS dark', osDark: true, expectedPreference: 'system' },
    { name: 'fresh, OS light', osDark: false, expectedPreference: 'system' },
    {
      name: 'system, OS dark',
      seed: { [APPEARANCE_STORAGE_KEY]: 'system' },
      osDark: true,
      expectedPreference: 'system',
      expectedStorage: { [APPEARANCE_STORAGE_KEY]: 'system' },
    },
    {
      name: 'explicit light, OS dark',
      seed: { [APPEARANCE_STORAGE_KEY]: 'light' },
      osDark: true,
      expectedPreference: 'light',
      expectedStorage: { [APPEARANCE_STORAGE_KEY]: 'light' },
    },
    {
      name: 'explicit dark, OS light',
      seed: { [APPEARANCE_STORAGE_KEY]: 'dark' },
      osDark: false,
      expectedPreference: 'dark',
      expectedStorage: { [APPEARANCE_STORAGE_KEY]: 'dark' },
    },
    {
      name: 'new key wins and removes stale legacy key',
      seed: { [APPEARANCE_STORAGE_KEY]: 'system', [LEGACY_THEME_KEY]: 'dark' },
      osDark: false,
      expectedPreference: 'system',
      expectedStorage: { [APPEARANCE_STORAGE_KEY]: 'system' },
    },
    {
      name: 'legacy light migrates while OS is dark',
      seed: { [LEGACY_THEME_KEY]: 'light' },
      osDark: true,
      expectedPreference: 'light',
      expectedStorage: { [APPEARANCE_STORAGE_KEY]: 'light' },
    },
    {
      name: 'legacy dark migrates while OS is light',
      seed: { [LEGACY_THEME_KEY]: 'dark' },
      osDark: false,
      expectedPreference: 'dark',
      expectedStorage: { [APPEARANCE_STORAGE_KEY]: 'dark' },
    },
    {
      name: 'garbage values fall back to System',
      seed: { [APPEARANCE_STORAGE_KEY]: 'x', [LEGACY_THEME_KEY]: 'y' },
      osDark: true,
      expectedPreference: 'system',
      expectedStorage: { [APPEARANCE_STORAGE_KEY]: 'x', [LEGACY_THEME_KEY]: 'y' },
    },
    {
      name: 'getItem failure falls back to System',
      seed: { [LEGACY_THEME_KEY]: 'dark' },
      failure: 'getItem',
      osDark: false,
      expectedPreference: 'system',
      expectedStorage: { [LEGACY_THEME_KEY]: 'dark' },
    },
    {
      name: 'setItem failure still honors the legacy value',
      seed: { [LEGACY_THEME_KEY]: 'dark' },
      failure: 'setItem',
      osDark: false,
      expectedPreference: 'dark',
      expectedStorage: { [LEGACY_THEME_KEY]: 'dark' },
    },
    {
      name: 'removeItem failure still honors the migrated legacy value',
      seed: { [LEGACY_THEME_KEY]: 'dark' },
      failure: 'removeItem',
      osDark: false,
      expectedPreference: 'dark',
      expectedStorage: { [APPEARANCE_STORAGE_KEY]: 'dark', [LEGACY_THEME_KEY]: 'dark' },
    },
    {
      name: 'removeItem failure still honors the authoritative new key',
      seed: { [APPEARANCE_STORAGE_KEY]: 'light', [LEGACY_THEME_KEY]: 'dark' },
      failure: 'removeItem',
      osDark: true,
      expectedPreference: 'light',
      expectedStorage: { [APPEARANCE_STORAGE_KEY]: 'light', [LEGACY_THEME_KEY]: 'dark' },
    },
  ];

  it.each(cases)(
    'matches the app preference, DOM attributes, and storage effects: $name',
    ({ seed = {}, failure, osDark, expectedPreference, expectedStorage = {} }) => {
      os = mockColorScheme(osDark);
      const boot = evaluateAppearance('boot', seed, failure);
      const app = evaluateAppearance('app', seed, failure);

      expect(boot).toEqual(app);
      expect(boot.preference).toBe(expectedPreference);
      expect(boot.resolved).toBe(resolveTheme(expectedPreference, osDark));
      expect(boot.dark).toBe(boot.resolved === 'dark');
      expect(boot.storage).toEqual(expectedStorage);
    },
  );

  it('matches the System fallback when the localStorage getter throws', () => {
    os = mockColorScheme(true);
    const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      get() {
        throw new Error('denied');
      },
    });
    try {
      expect(() => runBoot()).not.toThrow();
      expect(html().dataset.appearance).toBe('system');
      expect(html().classList.contains('dark')).toBe(true);
      expect(html().style.colorScheme).toBe('dark');
      expect(readPreference()).toBe('system');
    } finally {
      if (descriptor) Object.defineProperty(globalThis, 'localStorage', descriptor);
      else delete (globalThis as { localStorage?: Storage }).localStorage;
    }
  });
});
