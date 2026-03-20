import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useApiHealth } from '@/hooks/use-api-health';

// Mock @tanstack/react-query
const mockSubscribe = vi.fn();
const mockGetQueryCache = vi.fn(() => ({
  subscribe: mockSubscribe,
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({
    getQueryCache: mockGetQueryCache,
  }),
}));

// Mock the store - capture the selector calls to return stable references
const mockRecordFailure = vi.fn();
const mockRecordSuccess = vi.fn();

vi.mock('@/stores/api-health-store', () => ({
  useApiHealthStore: (selector: (s: Record<string, unknown>) => unknown) => {
    const state = {
      recordFailure: mockRecordFailure,
      recordSuccess: mockRecordSuccess,
    };
    return selector(state);
  },
}));

describe('useApiHealth', () => {
  let subscriberCallback: (event: Record<string, unknown>) => void;

  beforeEach(() => {
    vi.clearAllMocks();

    // Capture the callback passed to queryCache.subscribe
    mockSubscribe.mockImplementation((cb: (event: Record<string, unknown>) => void) => {
      subscriberCallback = cb;
      return vi.fn(); // unsubscribe function
    });
  });

  it('should subscribe to query cache events on mount', () => {
    renderHook(() => useApiHealth());

    expect(mockGetQueryCache).toHaveBeenCalled();
    expect(mockSubscribe).toHaveBeenCalledWith(expect.any(Function));
  });

  it('should call recordFailure when an error event with idle fetchStatus is received', () => {
    renderHook(() => useApiHealth());

    subscriberCallback({
      type: 'updated',
      query: {
        state: { status: 'error', fetchStatus: 'idle' },
      },
    });

    expect(mockRecordFailure).toHaveBeenCalledTimes(1);
    expect(mockRecordSuccess).not.toHaveBeenCalled();
  });

  it('should not call recordFailure for error events with non-idle fetchStatus', () => {
    renderHook(() => useApiHealth());

    subscriberCallback({
      type: 'updated',
      query: {
        state: { status: 'error', fetchStatus: 'fetching' },
      },
    });

    expect(mockRecordFailure).not.toHaveBeenCalled();
  });

  it('should call recordSuccess when a success event is received', () => {
    renderHook(() => useApiHealth());

    subscriberCallback({
      type: 'updated',
      query: {
        state: { status: 'success', fetchStatus: 'idle' },
      },
    });

    expect(mockRecordSuccess).toHaveBeenCalledTimes(1);
    expect(mockRecordFailure).not.toHaveBeenCalled();
  });

  it('should ignore events without a query', () => {
    renderHook(() => useApiHealth());

    subscriberCallback({ type: 'updated' });

    expect(mockRecordFailure).not.toHaveBeenCalled();
    expect(mockRecordSuccess).not.toHaveBeenCalled();
  });

  it('should ignore non-updated event types', () => {
    renderHook(() => useApiHealth());

    subscriberCallback({
      type: 'added',
      query: {
        state: { status: 'error', fetchStatus: 'idle' },
      },
    });

    expect(mockRecordFailure).not.toHaveBeenCalled();
    expect(mockRecordSuccess).not.toHaveBeenCalled();
  });

  it('should unsubscribe on unmount', () => {
    const mockUnsubscribe = vi.fn();
    mockSubscribe.mockReturnValue(mockUnsubscribe);

    const { unmount } = renderHook(() => useApiHealth());
    unmount();

    expect(mockUnsubscribe).toHaveBeenCalled();
  });
});
