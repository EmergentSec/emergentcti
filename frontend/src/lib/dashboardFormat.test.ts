import { describe, it, expect } from 'vitest';
import { compactNumber, pct, vsAvgDelta } from './dashboardFormat';

describe('dashboardFormat', () => {
  it('compactNumber', () => {
    expect(compactNumber(1482930)).toBe('1.48M');
    expect(compactNumber(12408)).toBe('12.4K');
    expect(compactNumber(11)).toBe('11');
  });
  it('pct', () => {
    expect(pct(43, 100)).toBe(43);
    expect(pct(1, 0)).toBe(0);
  });
  it('vsAvgDelta', () => {
    expect(vsAvgDelta(120, [{ count: 100 }, { count: 100 }])).toBe(20);
    expect(vsAvgDelta(100, [])).toBeNull();
  });
});
