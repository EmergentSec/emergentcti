import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { KpiCards } from './KpiCards';

const stats = {
  total_observables: 1482930, total_feeds: 13, feeds_enabled: 11,
  last_24h_ingested: 12408, feed_errors_24h: 1, by_type: {}, feeds_health: [
    { id: 'x', name: 'AbuseIPDB', enabled: true, last_run_status: 'failure', last_run_at: null, observable_count: 0 },
  ], confidence_distribution: { critical: 0, high: 0, medium: 0, low: 0 },
  daily_ingest_14d: Array.from({ length: 14 }, () => ({ date: '', count: 10000 })),
} as any;

describe('KpiCards', () => {
  it('renders the four KPIs with real values', () => {
    render(<KpiCards stats={stats} />);
    expect(screen.getByText('1,482,930')).toBeTruthy();
    expect(screen.getByText('11 / 13')).toBeTruthy();
    expect(screen.getByText('12,408')).toBeTruthy();
    expect(screen.getByText(/AbuseIPDB/)).toBeTruthy();   // failing-feed subtitle
  });
});
