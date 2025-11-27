'use client';

import { useState, useEffect, useCallback, useRef } from 'react';

// Default refresh interval: 5 minutes
const DEFAULT_INTERVAL_MS = 5 * 60 * 1000;

interface UseRefreshCountdownOptions {
  intervalMs?: number;
  onRefresh?: () => void | Promise<void>;
  autoStart?: boolean;
}

interface RefreshCountdownState {
  remainingMs: number;
  progress: number; // 0 to 1
  isRefreshing: boolean;
  isPaused: boolean;
}

export function useRefreshCountdown(options: UseRefreshCountdownOptions = {}) {
  const {
    intervalMs = DEFAULT_INTERVAL_MS,
    onRefresh,
    autoStart = true,
  } = options;

  const [state, setState] = useState<RefreshCountdownState>({
    remainingMs: intervalMs,
    progress: 1,
    isRefreshing: false,
    isPaused: !autoStart,
  });

  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const lastTickRef = useRef<number>(Date.now());
  const remainingRef = useRef(intervalMs);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  const triggerRefresh = useCallback(async () => {
    setState((prev) => ({ ...prev, isRefreshing: true }));

    try {
      await onRefresh?.();
    } catch (error) {
      console.error('Refresh failed:', error);
    } finally {
      // Reset countdown
      remainingRef.current = intervalMs;
      lastTickRef.current = Date.now();

      setState((prev) => ({
        ...prev,
        remainingMs: intervalMs,
        progress: 1,
        isRefreshing: false,
      }));
    }
  }, [onRefresh, intervalMs]);

  const updateCountdown = useCallback(() => {
    const now = Date.now();
    const elapsed = now - lastTickRef.current;
    lastTickRef.current = now;

    remainingRef.current = Math.max(0, remainingRef.current - elapsed);

    setState((prev) => ({
      ...prev,
      remainingMs: remainingRef.current,
      progress: remainingRef.current / intervalMs,
    }));

    // Trigger refresh when countdown reaches 0
    if (remainingRef.current <= 0) {
      triggerRefresh();
    }
  }, [intervalMs, triggerRefresh]);

  const start = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    lastTickRef.current = Date.now();

    intervalRef.current = setInterval(updateCountdown, 1000);

    setState((prev) => ({ ...prev, isPaused: false }));
  }, [updateCountdown]);

  const pause = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    setState((prev) => ({ ...prev, isPaused: true }));
  }, []);

  const reset = useCallback(() => {
    remainingRef.current = intervalMs;
    lastTickRef.current = Date.now();

    setState((prev) => ({
      ...prev,
      remainingMs: intervalMs,
      progress: 1,
    }));
  }, [intervalMs]);

  const manualRefresh = useCallback(() => {
    pause();
    triggerRefresh().then(() => {
      if (!state.isPaused) {
        start();
      }
    });
  }, [pause, triggerRefresh, start, state.isPaused]);

  // Auto-start on mount
  useEffect(() => {
    if (autoStart) {
      start();
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [autoStart, start]);

  // Format helpers
  const formatTime = useCallback((ms: number) => {
    const totalSeconds = Math.ceil(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }, []);

  return {
    // State
    remainingMs: state.remainingMs,
    progress: state.progress,
    isRefreshing: state.isRefreshing,
    isPaused: state.isPaused,

    // Formatted
    formattedTime: formatTime(state.remainingMs),

    // Actions
    start,
    pause,
    reset,
    refresh: manualRefresh,
  };
}

// Export the default interval for use in components
export const REFRESH_INTERVAL_MS = DEFAULT_INTERVAL_MS;
