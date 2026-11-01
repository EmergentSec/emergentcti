// Controllable `prefers-color-scheme` mock for appearance tests.
type Listener = (e: MediaQueryListEvent) => void;

export interface MockColorScheme {
  setDark: (dark: boolean) => void;
  listenerCount: () => number;
  restore: () => void;
}

export function mockColorScheme(
  initialDark: boolean,
  { legacyListeners = false }: { legacyListeners?: boolean } = {},
): MockColorScheme {
  let dark = initialDark;
  const listeners = new Set<Listener>();
  const original = window.matchMedia;

  window.matchMedia = ((query: string) => {
    const isDarkQuery = query.includes('prefers-color-scheme: dark');
    const mql = {
      get matches() {
        return isDarkQuery ? dark : false;
      },
      media: query,
      onchange: null,
      addListener: (l: Listener) => isDarkQuery && listeners.add(l),
      removeListener: (l: Listener) => listeners.delete(l),
      dispatchEvent: () => true,
    } as unknown as MediaQueryList;

    if (!legacyListeners) {
      Object.assign(mql, {
        addEventListener: (_: string, l: Listener) => isDarkQuery && listeners.add(l),
        removeEventListener: (_: string, l: Listener) => listeners.delete(l),
      });
    }

    return mql;
  }) as typeof window.matchMedia;

  return {
    setDark(next) {
      dark = next;
      listeners.forEach((l) => l({ matches: next } as MediaQueryListEvent));
    },
    listenerCount: () => listeners.size,
    restore() {
      window.matchMedia = original;
    },
  };
}
