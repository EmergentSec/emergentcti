import { describe, expect, it } from 'vitest';
import type { ObservableSource } from './observable';
import type { DashboardStats } from './dashboard';
import type { InstanceConfig } from './settings';

describe('type shapes', () => {
  it('carry the new foundation fields', () => {
    const src: ObservableSource = {
      feed_id: 'f', feed_name: 'n', source_confidence: 50, native_confidence: 80,
      first_seen_by_feed: '', last_seen_by_feed: '',
    };
    const stats: Pick<DashboardStats, 'confidence_distribution' | 'feed_errors_24h'> = {
      confidence_distribution: { critical: 1, high: 0, medium: 0, low: 0 },
      feed_errors_24h: 0,
    };
    const cfg: Pick<InstanceConfig, 'instance_name'> = { instance_name: 'EmergentCTI' };
    expect(src.native_confidence + stats.feed_errors_24h).toBe(80);
    expect(cfg.instance_name).toBe('EmergentCTI');
  });
});
