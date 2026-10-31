import { useEffect, useState } from 'react';

/** Tailwind `lg` breakpoint: persistent sidebar at and above, drawer below. */
export const DESKTOP_QUERY = '(min-width: 1024px)';

function matches(query: string, fallback: boolean): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return fallback;
  return window.matchMedia(query).matches;
}

/** Live `matchMedia` result. `fallback` is used where matchMedia is unavailable. */
export function useMediaQuery(query: string, fallback = true): boolean {
  const [value, setValue] = useState(() => matches(query, fallback));

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const mql = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => setValue(e.matches);
    setValue(mql.matches);
    mql.addEventListener?.('change', onChange);
    return () => mql.removeEventListener?.('change', onChange);
  }, [query]);

  return value;
}
