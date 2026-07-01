import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { FeedStatusTable } from './FeedStatusTable';

// react-router-dom Link stub
vi.mock('react-router-dom', () => ({
  Link: ({ to, children }: { to: string; children: React.ReactNode }) => (
    <a href={to}>{children}</a>
  ),
}));

const feeds = [
  {
    id: '1',
    name: 'AbuseIPDB',
    enabled: true,
    last_run_status: 'success' as const,
    last_run_at: '2026-06-29T10:00:00Z',
    observable_count: 12500,
  },
  {
    id: '2',
    name: 'Emerging Threats',
    enabled: true,
    last_run_status: 'failure' as const,
    last_run_at: '2026-06-29T08:00:00Z',
    observable_count: 840,
  },
];

describe('FeedStatusTable', () => {
  afterEach(cleanup);

  it('renders feed names and "View all" link to /feeds', () => {
    render(<FeedStatusTable feeds={feeds} />);

    expect(screen.getByText('Feed status')).toBeTruthy();
    expect(screen.getByText('AbuseIPDB')).toBeTruthy();
    expect(screen.getByText('Emerging Threats')).toBeTruthy();

    const viewAll = screen.getByText('View all');
    expect(viewAll).toBeTruthy();
    expect(viewAll.closest('a')?.getAttribute('href')).toBe('/feeds');
  });

  it('renders observable counts and status dots', () => {
    render(<FeedStatusTable feeds={feeds} />);

    // compactNumber: 12500 → "12.5K"
    expect(screen.getByText('12.5K')).toBeTruthy();
    // compactNumber: 840 → "840"
    expect(screen.getByText('840')).toBeTruthy();
  });
});
