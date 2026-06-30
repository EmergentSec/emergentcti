export function compactNumber(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 1)}K`.replace('.0K', 'K');
  return `${(n / 1_000_000).toFixed(2)}M`.replace(/\.?0+M$/, 'M');
}

export function pct(part: number, total: number): number {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

export function vsAvgDelta(today: number, series: { count: number }[]): number | null {
  if (!series.length) return null;
  const mean = series.reduce((s, p) => s + p.count, 0) / series.length;
  if (!mean) return null;
  return Math.round(((today - mean) / mean) * 100);
}
