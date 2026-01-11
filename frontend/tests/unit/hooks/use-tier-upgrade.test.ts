/**
 * Unit tests for useTierUpgrade hook.
 *
 * Feature: 1191 - Mid-Session Tier Upgrade
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useTierUpgrade } from '@/hooks/use-tier-upgrade';

// Mock dependencies
vi.mock('@/stores/auth-store', () => ({
  useAuthStore: vi.fn((selector) => {
    const state = {
      user: { userId: 'user_123', role: 'free' },
      setUser: vi.fn(),
    };
    return selector(state);
  }),
}));

vi.mock('@/lib/api', () => ({
  authApi: {
    getProfile: vi.fn(),
  },
}));

vi.mock('@/lib/sync/broadcast-channel', () => ({
  getAuthBroadcastSync: () => ({
    broadcast: vi.fn(),
  }),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    info: vi.fn(),
  },
}));

describe('useTierUpgrade', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('should initialize with default state', () => {
    const { result } = renderHook(() => useTierUpgrade());

    expect(result.current.state).toEqual({
      isPolling: false,
      attemptCount: 0,
      success: false,
      timedOut: false,
      error: null,
    });
  });

  it('should set isPolling to true when startPolling is called', async () => {
    const { authApi } = await import('@/lib/api');
    vi.mocked(authApi.getProfile).mockResolvedValue({ role: 'free' });

    const { result } = renderHook(() => useTierUpgrade());

    // Start polling (don't await, just trigger)
    act(() => {
      result.current.startPolling();
    });

    expect(result.current.state.isPolling).toBe(true);
  });

  it('should increment attemptCount on each poll', async () => {
    const { authApi } = await import('@/lib/api');
    // Always return 'free' role (no upgrade detected)
    vi.mocked(authApi.getProfile).mockResolvedValue({ role: 'free' });

    const { result } = renderHook(() => useTierUpgrade());

    // Start polling
    act(() => {
      result.current.startPolling();
    });

    // Advance through first interval (1s)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(result.current.state.attemptCount).toBe(1);

    // Advance through second interval (2s)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(result.current.state.attemptCount).toBe(2);
  });

  it('should detect role upgrade and set success', async () => {
    const { authApi } = await import('@/lib/api');
    const { toast } = await import('sonner');

    // First call: still 'free', second call: upgraded to 'paid'
    vi.mocked(authApi.getProfile)
      .mockResolvedValueOnce({ role: 'free' })
      .mockResolvedValueOnce({ role: 'paid', subscriptionActive: true });

    const { result } = renderHook(() => useTierUpgrade());

    let pollingPromise: Promise<boolean>;
    act(() => {
      pollingPromise = result.current.startPolling();
    });

    // Advance through first interval
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    // Advance through second interval
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    // Wait for promise to resolve
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(result.current.state.success).toBe(true);
    expect(result.current.state.isPolling).toBe(false);
    expect(toast.success).toHaveBeenCalled();
  });

  it('should timeout after all intervals exhausted', async () => {
    const { authApi } = await import('@/lib/api');
    const { toast } = await import('sonner');

    // Always return 'free' role
    vi.mocked(authApi.getProfile).mockResolvedValue({ role: 'free' });

    const { result } = renderHook(() => useTierUpgrade());

    act(() => {
      result.current.startPolling();
    });

    // Advance through all intervals (60s total)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60000);
    });

    expect(result.current.state.timedOut).toBe(true);
    expect(result.current.state.success).toBe(false);
    expect(result.current.state.isPolling).toBe(false);
    expect(toast.info).toHaveBeenCalled();
  });

  it('should stop polling when stopPolling is called', async () => {
    const { authApi } = await import('@/lib/api');
    vi.mocked(authApi.getProfile).mockResolvedValue({ role: 'free' });

    const { result } = renderHook(() => useTierUpgrade());

    act(() => {
      result.current.startPolling();
    });

    // Stop immediately
    act(() => {
      result.current.stopPolling();
    });

    // Advance timers
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(result.current.state.isPolling).toBe(false);
  });

  it('should reset state and restart on retry', async () => {
    const { authApi } = await import('@/lib/api');
    vi.mocked(authApi.getProfile).mockResolvedValue({ role: 'paid', subscriptionActive: true });

    const { result } = renderHook(() => useTierUpgrade());

    // First polling attempt
    act(() => {
      result.current.startPolling();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    // Retry
    act(() => {
      result.current.retry();
    });

    expect(result.current.state.attemptCount).toBe(0);
    expect(result.current.state.isPolling).toBe(true);
  });
});
