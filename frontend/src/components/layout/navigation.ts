import { CrosshairSimple, GearSix, Rss, SquaresFour, type Icon } from '@phosphor-icons/react';

export interface PageMeta {
  title: string;
  subtitle: string;
  icon: Icon;
}

/** Route → page-header metadata. Nested routes inherit their section's meta. */
export const PAGE_META: Record<string, PageMeta> = {
  '/': { title: 'Dashboard', subtitle: 'Aggregation overview & feed health', icon: SquaresFour },
  '/observables': { title: 'Observables', subtitle: 'Search and manage threat indicators', icon: CrosshairSimple },
  '/feeds': { title: 'Feeds', subtitle: 'Manage intelligence feed sources', icon: Rss },
  '/settings': { title: 'Settings', subtitle: 'Platform configuration', icon: GearSix },
};

export function getPageMeta(pathname: string): PageMeta | null {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;
  if (PAGE_META[path]) return PAGE_META[path];
  // e.g. /observables/:id → Observables
  const section = `/${path.split('/')[1] ?? ''}`;
  return section !== '/' ? PAGE_META[section] ?? null : null;
}

export type NavCount = 'observables' | 'feeds';

export const NAV_ITEMS: { to: string; label: string; icon: Icon; end?: boolean; count?: NavCount }[] = [
  { to: '/', label: 'Dashboard', icon: SquaresFour, end: true },
  { to: '/observables', label: 'Observables', icon: CrosshairSimple, count: 'observables' },
  { to: '/feeds', label: 'Feeds', icon: Rss, count: 'feeds' },
  { to: '/settings', label: 'Settings', icon: GearSix },
];
