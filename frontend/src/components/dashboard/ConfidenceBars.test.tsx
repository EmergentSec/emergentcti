import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import { ConfidenceBars } from './ConfidenceBars';

describe('ConfidenceBars', () => {
  afterEach(cleanup);

  it('renders all four band labels and counts', () => {
    render(
      <ConfidenceBars distribution={{ critical: 5, high: 3, medium: 2, low: 1 }} />
    );

    expect(screen.getByText('Confidence distribution')).toBeTruthy();

    // Band labels
    expect(screen.getByText('Critical')).toBeTruthy();
    expect(screen.getByText('High')).toBeTruthy();
    expect(screen.getByText('Medium')).toBeTruthy();
    expect(screen.getByText('Low')).toBeTruthy();

    // Counts
    expect(screen.getByText('5')).toBeTruthy();
    expect(screen.getByText('3')).toBeTruthy();
    expect(screen.getByText('2')).toBeTruthy();
    expect(screen.getByText('1')).toBeTruthy();
  });

  it('renders range labels for each band', () => {
    render(
      <ConfidenceBars distribution={{ critical: 5, high: 3, medium: 2, low: 1 }} />
    );

    expect(screen.getByText('80–100')).toBeTruthy();
    expect(screen.getByText('60–79')).toBeTruthy();
    expect(screen.getByText('40–59')).toBeTruthy();
    expect(screen.getByText('0–39')).toBeTruthy();
  });
});
