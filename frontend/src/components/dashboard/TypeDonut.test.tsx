import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TypeDonut } from './TypeDonut';

const byType = {
  'ip-addr': 640,
  'url': 357,
  'domain-name': 253,
  'file-hash': 149,
  'email-addr': 59,
  'command-line': 30,
};
const total = Object.values(byType).reduce((s, n) => s + n, 0); // 1488

describe('TypeDonut', () => {
  it('renders card title, legend labels, and at least one percentage', () => {
    render(<TypeDonut byType={byType} total={total} />);
    expect(screen.getByText('Observable types')).toBeTruthy();
    expect(screen.getByText('IP Address')).toBeTruthy();
    expect(screen.getByText('URL')).toBeTruthy();
    // at least one % value is present
    const pctEls = screen.getAllByText(/%$/);
    expect(pctEls.length).toBeGreaterThan(0);
  });
});
