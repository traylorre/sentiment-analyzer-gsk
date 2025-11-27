import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useRefreshCountdown, REFRESH_INTERVAL_MS } from '@/hooks/use-refresh-countdown';

describe('useRefreshCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('initial state', () => {
    it('should start with full countdown', () => {
      const { result } = renderHook(() => useRefreshCountdown({ autoStart: false }));

      expect(result.current.remainingMs).toBe(REFRESH_INTERVAL_MS);
      expect(result.current.progress).toBe(1);
      expect(result.current.isRefreshing).toBe(false);
    });

    it('should use custom interval', () => {
      const customInterval = 60000; // 1 minute
      const { result } = renderHook(() =>
        useRefreshCountdown({ intervalMs: customInterval, autoStart: false })
      );

      expect(result.current.remainingMs).toBe(customInterval);
    });

    it('should start paused when autoStart is false', () => {
      const { result } = renderHook(() =>
        useRefreshCountdown({ autoStart: false })
      );

      expect(result.current.isPaused).toBe(true);
    });

    it('should start counting when autoStart is true', () => {
      const { result } = renderHook(() =>
        useRefreshCountdown({ autoStart: true })
      );

      expect(result.current.isPaused).toBe(false);
    });
  });

  describe('countdown behavior', () => {
    it('should decrease remainingMs over time', () => {
      const { result } = renderHook(() =>
        useRefreshCountdown({ intervalMs: 10000, autoStart: true })
      );

      const initialRemaining = result.current.remainingMs;

      act(() => {
        vi.advanceTimersByTime(2000);
      });

      expect(result.current.remainingMs).toBeLessThan(initialRemaining);
    });

    it('should update progress as time passes', () => {
      const { result } = renderHook(() =>
        useRefreshCountdown({ intervalMs: 10000, autoStart: true })
      );

      act(() => {
        vi.advanceTimersByTime(5000);
      });

      // Progress should be approximately 0.5 (halfway)
      expect(result.current.progress).toBeCloseTo(0.5, 1);
    });
  });

  describe('manual actions', () => {
    it('should pause countdown', () => {
      const { result } = renderHook(() =>
        useRefreshCountdown({ intervalMs: 10000, autoStart: true })
      );

      act(() => {
        result.current.pause();
      });

      expect(result.current.isPaused).toBe(true);
    });

    it('should resume countdown with start', () => {
      const { result } = renderHook(() =>
        useRefreshCountdown({ intervalMs: 10000, autoStart: false })
      );

      expect(result.current.isPaused).toBe(true);

      act(() => {
        result.current.start();
      });

      expect(result.current.isPaused).toBe(false);
    });

    it('should reset countdown to full', () => {
      const { result } = renderHook(() =>
        useRefreshCountdown({ intervalMs: 10000, autoStart: true })
      );

      act(() => {
        vi.advanceTimersByTime(5000);
      });

      expect(result.current.remainingMs).toBeLessThan(10000);

      act(() => {
        result.current.reset();
      });

      expect(result.current.remainingMs).toBe(10000);
      expect(result.current.progress).toBe(1);
    });
  });

  describe('formatted time', () => {
    it('should format time as MM:SS', () => {
      const { result } = renderHook(() =>
        useRefreshCountdown({ intervalMs: 125000, autoStart: false }) // 2:05
      );

      expect(result.current.formattedTime).toBe('2:05');
    });

    it('should pad seconds with zero', () => {
      const { result } = renderHook(() =>
        useRefreshCountdown({ intervalMs: 65000, autoStart: false }) // 1:05
      );

      expect(result.current.formattedTime).toBe('1:05');
    });

    it('should format 5 minutes correctly', () => {
      const { result } = renderHook(() =>
        useRefreshCountdown({ intervalMs: 300000, autoStart: false }) // 5:00
      );

      expect(result.current.formattedTime).toBe('5:00');
    });
  });

  describe('cleanup', () => {
    it('should clear interval on unmount', () => {
      const clearIntervalSpy = vi.spyOn(global, 'clearInterval');

      const { unmount } = renderHook(() =>
        useRefreshCountdown({ intervalMs: 10000, autoStart: true })
      );

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
      clearIntervalSpy.mockRestore();
    });
  });
});

describe('REFRESH_INTERVAL_MS', () => {
  it('should be 5 minutes', () => {
    expect(REFRESH_INTERVAL_MS).toBe(5 * 60 * 1000);
  });
});
