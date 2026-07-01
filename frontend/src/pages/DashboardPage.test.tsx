import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import DashboardPage from './DashboardPage';

vi.mock('@/hooks/useDashboard', () => ({
  useDashboard: () => ({
    isLoading: false,
    error: null,
    data: {
      total_observables: 1482930,
      total_feeds: 13,
      feeds_enabled: 11,
      last_24h_ingested: 12408,
      feed_errors_24h: 1,
      by_type: { 'ip-addr': 100 },
      feeds_health: [],
      confidence_distribution: { critical: 1, high: 1, medium: 1, low: 1 },
      daily_ingest_14d: Array.from({ length: 14 }, (_, i) => ({ date: `d${i}`, count: 100 })),
    },
  }),
}));

describe('DashboardPage', () => {
  it('renders the redesigned sections', () => {
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getAllByText('1,482,930').length).toBeGreaterThan(0); // KPI + donut center
    expect(screen.getByText('Ingestion volume')).toBeTruthy();    // chart card
    expect(screen.getByText('Observable types')).toBeTruthy();    // donut card
    expect(screen.getByText('Confidence distribution')).toBeTruthy();
  });
});
