/**
 * Feature 1226: API Health State Store
 *
 * Tracks the outcomes of user-triggered API requests to detect
 * sustained connectivity failures. No polling — purely passive.
 *
 * State transitions (from data-model.md):
 *   HEALTHY → recordFailure() × 3 in 60s → UNREACHABLE
 *   UNREACHABLE → recordSuccess() → HEALTHY
 *   UNREACHABLE → dismissBanner() → UNREACHABLE (banner hidden)
 */

import { create } from 'zustand';

const FAILURE_WINDOW_MS = 60_000; // 60 seconds
const FAILURE_THRESHOLD = 3;

interface ApiHealthState {
  failures: number[]; // timestamps of recent failures
  isUnreachable: boolean;
  bannerDismissed: boolean;
}

interface ApiHealthActions {
  recordFailure: () => void;
  recordSuccess: () => void;
  dismissBanner: () => void;
}

type ApiHealthStore = ApiHealthState & ApiHealthActions;

export const useApiHealthStore = create<ApiHealthStore>((set, get) => ({
  failures: [],
  isUnreachable: false,
  bannerDismissed: false,

  recordFailure: () => {
    const now = Date.now();
    const cutoff = now - FAILURE_WINDOW_MS;
    const { failures } = get();

    // Prune old entries and add new failure
    const updated = [...failures.filter((t) => t > cutoff), now];

    const isUnreachable = updated.length >= FAILURE_THRESHOLD;

    set({
      failures: updated,
      isUnreachable,
      // Reset dismissed when transitioning to a new unreachable cycle
      ...(isUnreachable && !get().isUnreachable ? { bannerDismissed: false } : {}),
    });
  },

  recordSuccess: () => {
    set({
      failures: [],
      isUnreachable: false,
      bannerDismissed: false,
    });
  },

  dismissBanner: () => {
    set({ bannerDismissed: true });
  },
}));

// Selectors for fine-grained subscriptions
export const selectIsUnreachable = (state: ApiHealthStore) => state.isUnreachable;
export const selectBannerVisible = (state: ApiHealthStore) =>
  state.isUnreachable && !state.bannerDismissed;
export const selectFailureCount = (state: ApiHealthStore) => state.failures.length;
