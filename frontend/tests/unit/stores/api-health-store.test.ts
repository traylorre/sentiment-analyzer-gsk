import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  useApiHealthStore,
  selectIsUnreachable,
  selectBannerVisible,
  selectFailureCount,
} from '@/stores/api-health-store';

describe('API Health Store', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useApiHealthStore.setState({
      failures: [],
      isUnreachable: false,
      bannerDismissed: false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('recordFailure', () => {
    it('should accumulate failures within the 60s window', () => {
      const { recordFailure } = useApiHealthStore.getState();

      recordFailure();
      expect(useApiHealthStore.getState().failures).toHaveLength(1);

      vi.advanceTimersByTime(10_000);
      recordFailure();
      expect(useApiHealthStore.getState().failures).toHaveLength(2);
    });

    it('should prune failures older than 60s', () => {
      const { recordFailure } = useApiHealthStore.getState();

      recordFailure();
      expect(useApiHealthStore.getState().failures).toHaveLength(1);

      // Advance past the 60s window
      vi.advanceTimersByTime(61_000);

      recordFailure();
      // The first failure should have been pruned
      expect(useApiHealthStore.getState().failures).toHaveLength(1);
    });

    it('should transition to isUnreachable at exactly 3 failures', () => {
      const { recordFailure } = useApiHealthStore.getState();

      recordFailure();
      expect(useApiHealthStore.getState().isUnreachable).toBe(false);

      recordFailure();
      expect(useApiHealthStore.getState().isUnreachable).toBe(false);

      recordFailure();
      expect(useApiHealthStore.getState().isUnreachable).toBe(true);
    });

    it('should not transition to unreachable if failures span beyond 60s', () => {
      const { recordFailure } = useApiHealthStore.getState();

      recordFailure();
      vi.advanceTimersByTime(30_000);

      recordFailure();
      vi.advanceTimersByTime(31_000); // first failure is now >60s old

      recordFailure();
      // Only 2 failures in window (the second and third)
      expect(useApiHealthStore.getState().isUnreachable).toBe(false);
      expect(useApiHealthStore.getState().failures).toHaveLength(2);
    });
  });

  describe('recordSuccess', () => {
    it('should clear failures and reset isUnreachable', () => {
      const { recordFailure, recordSuccess } = useApiHealthStore.getState();

      recordFailure();
      recordFailure();
      recordFailure();
      expect(useApiHealthStore.getState().isUnreachable).toBe(true);

      recordSuccess();
      expect(useApiHealthStore.getState().failures).toHaveLength(0);
      expect(useApiHealthStore.getState().isUnreachable).toBe(false);
    });

    it('should reset bannerDismissed', () => {
      const { recordFailure, dismissBanner, recordSuccess } =
        useApiHealthStore.getState();

      recordFailure();
      recordFailure();
      recordFailure();
      dismissBanner();
      expect(useApiHealthStore.getState().bannerDismissed).toBe(true);

      recordSuccess();
      expect(useApiHealthStore.getState().bannerDismissed).toBe(false);
    });
  });

  describe('dismissBanner', () => {
    it('should set bannerDismissed without changing isUnreachable', () => {
      const { recordFailure, dismissBanner } = useApiHealthStore.getState();

      recordFailure();
      recordFailure();
      recordFailure();
      expect(useApiHealthStore.getState().isUnreachable).toBe(true);

      dismissBanner();
      expect(useApiHealthStore.getState().bannerDismissed).toBe(true);
      expect(useApiHealthStore.getState().isUnreachable).toBe(true);
    });
  });

  describe('recovery cycle', () => {
    it('should reset bannerDismissed when going unreachable -> success -> unreachable', () => {
      const { recordFailure, dismissBanner, recordSuccess } =
        useApiHealthStore.getState();

      // Phase 1: become unreachable and dismiss banner
      recordFailure();
      recordFailure();
      recordFailure();
      expect(useApiHealthStore.getState().isUnreachable).toBe(true);

      dismissBanner();
      expect(useApiHealthStore.getState().bannerDismissed).toBe(true);

      // Phase 2: recover
      recordSuccess();
      expect(useApiHealthStore.getState().isUnreachable).toBe(false);
      expect(useApiHealthStore.getState().bannerDismissed).toBe(false);

      // Phase 3: become unreachable again
      recordFailure();
      recordFailure();
      recordFailure();
      expect(useApiHealthStore.getState().isUnreachable).toBe(true);
      // bannerDismissed should be false for the new unreachable cycle
      expect(useApiHealthStore.getState().bannerDismissed).toBe(false);
    });
  });

  describe('selectors', () => {
    it('selectIsUnreachable returns isUnreachable state', () => {
      const { recordFailure } = useApiHealthStore.getState();

      expect(selectIsUnreachable(useApiHealthStore.getState())).toBe(false);

      recordFailure();
      recordFailure();
      recordFailure();

      expect(selectIsUnreachable(useApiHealthStore.getState())).toBe(true);
    });

    it('selectBannerVisible returns true when unreachable and not dismissed', () => {
      const { recordFailure, dismissBanner } = useApiHealthStore.getState();

      expect(selectBannerVisible(useApiHealthStore.getState())).toBe(false);

      recordFailure();
      recordFailure();
      recordFailure();
      expect(selectBannerVisible(useApiHealthStore.getState())).toBe(true);

      dismissBanner();
      expect(selectBannerVisible(useApiHealthStore.getState())).toBe(false);
    });

    it('selectBannerVisible returns false when not unreachable', () => {
      expect(selectBannerVisible(useApiHealthStore.getState())).toBe(false);
    });

    it('selectFailureCount returns the number of failures in window', () => {
      const { recordFailure } = useApiHealthStore.getState();

      expect(selectFailureCount(useApiHealthStore.getState())).toBe(0);

      recordFailure();
      expect(selectFailureCount(useApiHealthStore.getState())).toBe(1);

      recordFailure();
      expect(selectFailureCount(useApiHealthStore.getState())).toBe(2);

      // Advance past window so failures are pruned on next record
      vi.advanceTimersByTime(61_000);
      recordFailure();
      expect(selectFailureCount(useApiHealthStore.getState())).toBe(1);
    });
  });
});
