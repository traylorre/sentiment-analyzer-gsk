import { describe, it, expect } from 'vitest';
import {
  TIME_RANGE_ORDER,
  getNextTimeRange,
  shouldUpgradeTimeRange,
} from '@/types/chart';

describe('TIME_RANGE_ORDER', () => {
  it('should list ranges from narrowest to widest', () => {
    expect(TIME_RANGE_ORDER).toEqual(['1W', '1M', '3M', '6M', '1Y']);
  });
});

describe('getNextTimeRange', () => {
  it('1W -> 1M', () => expect(getNextTimeRange('1W')).toBe('1M'));
  it('1M -> 3M', () => expect(getNextTimeRange('1M')).toBe('3M'));
  it('3M -> 6M', () => expect(getNextTimeRange('3M')).toBe('6M'));
  it('6M -> 1Y', () => expect(getNextTimeRange('6M')).toBe('1Y'));
  it('1Y -> null (maximum)', () => expect(getNextTimeRange('1Y')).toBeNull());
});

describe('shouldUpgradeTimeRange', () => {
  it('returns false when dataLength is 0 (empty data)', () => {
    expect(shouldUpgradeTimeRange({ from: -5, to: 5 }, 0)).toBe(false);
  });

  it('returns false when visible range fits within data (zoom-in)', () => {
    // All data within bounds: from=2, to=18, dataLength=22
    expect(shouldUpgradeTimeRange({ from: 2, to: 18 }, 22)).toBe(false);
  });

  it('returns false when overshoot is below 30% threshold', () => {
    // 22 candles, 30% = 6.6. Left overshoot = 5, right overshoot = 0, total = 5 < 6.6
    expect(shouldUpgradeTimeRange({ from: -5, to: 21 }, 22)).toBe(false);
  });

  it('returns true when overshoot exceeds 30% threshold', () => {
    // 22 candles, 30% = 6.6. Left overshoot = 4, right = max(0, 26-21) = 5, total = 9 > 6.6
    expect(shouldUpgradeTimeRange({ from: -4, to: 26 }, 22)).toBe(true);
  });

  it('returns true for significant left-only overshoot', () => {
    // 22 candles, 30% = 6.6. Left overshoot = 10, right = 0, total = 10 > 6.6
    expect(shouldUpgradeTimeRange({ from: -10, to: 21 }, 22)).toBe(true);
  });

  it('returns true for significant right-only overshoot', () => {
    // 22 candles, 30% = 6.6. Left = 0, right = max(0, 31-21) = 10, total = 10 > 6.6
    expect(shouldUpgradeTimeRange({ from: 0, to: 31 }, 22)).toBe(true);
  });

  it('returns false when exactly at 30% boundary', () => {
    // 10 candles, 30% = 3.0. Left = 3, right = max(0, 9-9) = 0, total = 3 (not > 3)
    expect(shouldUpgradeTimeRange({ from: -3, to: 9 }, 10)).toBe(false);
  });

  it('returns true when just past 30% boundary', () => {
    // 10 candles, 30% = 3.0. Left = 3.1, right = 0, total = 3.1 > 3.0
    expect(shouldUpgradeTimeRange({ from: -3.1, to: 9 }, 10)).toBe(true);
  });

  it('handles small datasets (2 candles)', () => {
    // 2 candles, 30% = 0.6. Left = 1, right = 0, total = 1 > 0.6
    expect(shouldUpgradeTimeRange({ from: -1, to: 1 }, 2)).toBe(true);
    // 2 candles, Left = 0.5, right = 0, total = 0.5 < 0.6
    expect(shouldUpgradeTimeRange({ from: -0.5, to: 1 }, 2)).toBe(false);
  });
});
