'use client';

/**
 * Runtime configuration store
 * Feature 1100: SSE Runtime URL Discovery
 *
 * Stores runtime configuration fetched from /api/v2/runtime,
 * specifically the SSE Lambda URL for streaming connections.
 */

import { create } from 'zustand';
import type { RuntimeConfig, RuntimeState } from '@/types/runtime';
import { fetchRuntimeConfig } from '@/lib/api/runtime';

interface RuntimeActions {
  /** Initialize runtime config by fetching from backend */
  initialize: () => Promise<void>;
  /** Get the SSE base URL (returns SSE Lambda URL or falls back to API URL) */
  getSseBaseUrl: () => string;
  /** Reset store to initial state */
  reset: () => void;
}

type RuntimeStore = RuntimeState & RuntimeActions;

const initialState: RuntimeState = {
  config: null,
  isLoaded: false,
  isLoading: false,
  error: null,
};

export const useRuntimeStore = create<RuntimeStore>((set, get) => ({
  ...initialState,

  initialize: async () => {
    // Skip if already loaded or loading
    const { isLoaded, isLoading } = get();
    if (isLoaded || isLoading) {
      return;
    }

    set({ isLoading: true, error: null });

    try {
      const config = await fetchRuntimeConfig();

      if (config) {
        set({
          config,
          isLoaded: true,
          isLoading: false,
          error: null,
        });
      } else {
        // Fetch failed but we can still proceed with fallback
        set({
          config: null,
          isLoaded: true,
          isLoading: false,
          error: 'Failed to fetch runtime config',
        });
      }
    } catch (error) {
      set({
        config: null,
        isLoaded: true,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  },

  getSseBaseUrl: () => {
    const { config } = get();

    // If we have an SSE URL from runtime config, use it
    if (config?.sse_url) {
      // Remove trailing slash for consistency
      return config.sse_url.replace(/\/$/, '');
    }

    // Fall back to the main API URL (Dashboard Lambda)
    // This won't work for SSE but maintains backwards compatibility
    return (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
  },

  reset: () => set(initialState),
}));

// Selector hooks
export const useSseBaseUrl = () => {
  const getSseBaseUrl = useRuntimeStore((state) => state.getSseBaseUrl);
  return getSseBaseUrl();
};

export const useRuntimeLoaded = () => {
  return useRuntimeStore((state) => state.isLoaded);
};

export const useRuntimeEnvironment = () => {
  return useRuntimeStore((state) => state.config?.environment);
};
