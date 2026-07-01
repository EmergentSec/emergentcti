import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { IngestionTrend } from './IngestionTrend';

const series = [
  { date: '2026-06-01', count: 1200 },
  { date: '2026-06-02', count: 1400 },
  { date: '2026-06-03', count: 1100 },
];

describe('IngestionTrend', () => {
  it('renders the card title and formatted 14-day total', () => {
    render(<IngestionTrend series={series} />);
    expect(screen.getByText('Ingestion volume')).toBeTruthy();
    // total = 1200 + 1400 + 1100 = 3700
    expect(screen.getByText('3,700')).toBeTruthy();
  });
});
