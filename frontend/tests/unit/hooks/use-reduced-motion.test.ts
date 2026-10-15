import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useReducedMotion } from '@/hooks/use-reduced-motion';

function stubMatchMedia(initial: boolean) {
  let matches = initial;
  const listeners = new Set<(event: { matches: boolean }) => void>();
  const mql = {
    get matches() {
      return matches;
    },
    addEventListener: vi.fn((_: string, cb: (event: { matches: boolean }) => void) =>
      listeners.add(cb)
    ),
    removeEventListener: vi.fn((_: string, cb: (event: { matches: boolean }) => void) =>
      listeners.delete(cb)
    ),
  };
  const matchMedia = vi.mocked(window.matchMedia);
  const original = matchMedia.getMockImplementation();
  matchMedia.mockImplementation(() => mql as unknown as MediaQueryList);
  return {
    set(next: boolean) {
      matches = next;
      listeners.forEach((cb) => cb({ matches }));
    },
    listeners,
    restore: () => {
      matchMedia.mockImplementation(original!);
    },
  };
}

describe('useReducedMotion', () => {
  let media: ReturnType<typeof stubMatchMedia>;

  afterEach(() => media.restore());

  it('reports the OS preference on first render', () => {
    media = stubMatchMedia(true);
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
  });

  it('follows changes to the preference', () => {
    media = stubMatchMedia(false);
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);

    act(() => media.set(true));
    expect(result.current).toBe(true);
  });

  it('unsubscribes on unmount', () => {
    media = stubMatchMedia(false);
    const { unmount } = renderHook(() => useReducedMotion());
    expect(media.listeners.size).toBe(1);
    unmount();
    expect(media.listeners.size).toBe(0);
  });
});
