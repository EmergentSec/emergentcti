// Controllable `prefers-color-scheme` mock for appearance tests.
type Listener = (e: MediaQueryListEvent) => void;

export interface MockColorScheme {
  setDark: (dark: boolean) => void;
  listenerCount: () => number;
  restore: () => void;
}

export function mockColorScheme(initialDark: boolean): MockColorScheme {
  let dark = initialDark;
  const listeners = new Set<Listener>();
  const original = window.matchMedia;

  window.matchMedia = ((query: string) => {
    const isDarkQuery = query.includes('prefers-color-scheme: dark');
    return {
      get matches() {
        return isDarkQuery ? dark : false;
      },
      media: query,
      onchange: null,
      addEventListener: (_: string, l: Listener) => isDarkQuery && listeners.add(l),
      removeEventListener: (_: string, l: Listener) => listeners.delete(l),
      addListener: (l: Listener) => isDarkQuery && listeners.add(l),
      removeListener: (l: Listener) => listeners.delete(l),
      dispatchEvent: () => true,
    } as unknown as MediaQueryList;
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
