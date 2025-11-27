'use client';

import { useCallback, useRef, useEffect, useMemo } from 'react';
import { useViewStore } from '@/stores/view-store';
import { useHaptic } from './use-haptic';

interface GestureConfig {
  threshold?: number; // Minimum distance to trigger navigation (px)
  velocityThreshold?: number; // Minimum velocity to trigger (px/ms)
  direction?: 'horizontal' | 'vertical' | 'both';
  enabled?: boolean;
}

interface GestureHandlers {
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
  onSwipeUp?: () => void;
  onSwipeDown?: () => void;
  onPullDown?: (progress: number) => void;
  onPullRelease?: (shouldTrigger: boolean) => void;
}

interface TouchState {
  startX: number;
  startY: number;
  startTime: number;
  currentX: number;
  currentY: number;
  isTracking: boolean;
}

const DEFAULT_CONFIG: Required<GestureConfig> = {
  threshold: 50,
  velocityThreshold: 0.3,
  direction: 'horizontal',
  enabled: true,
};

export function useGesture(
  elementRef: React.RefObject<HTMLElement | null>,
  handlers: GestureHandlers = {},
  config: GestureConfig = {}
) {
  // Memoize merged config to prevent unnecessary re-renders
  const mergedConfig = useMemo(() => ({
    ...DEFAULT_CONFIG,
    ...config,
  }), [config]);
  const touchState = useRef<TouchState>({
    startX: 0,
    startY: 0,
    startTime: 0,
    currentX: 0,
    currentY: 0,
    isTracking: false,
  });

  const { startGesture, updateGesture, endGesture, cancelGesture } = useViewStore();
  const haptic = useHaptic();

  const handleTouchStart = useCallback(
    (e: TouchEvent) => {
      if (!mergedConfig.enabled) return;

      const touch = e.touches[0];
      touchState.current = {
        startX: touch.clientX,
        startY: touch.clientY,
        startTime: Date.now(),
        currentX: touch.clientX,
        currentY: touch.clientY,
        isTracking: true,
      };
    },
    [mergedConfig.enabled]
  );

  const handleTouchMove = useCallback(
    (e: TouchEvent) => {
      if (!mergedConfig.enabled || !touchState.current.isTracking) return;

      const touch = e.touches[0];
      const deltaX = touch.clientX - touchState.current.startX;
      const deltaY = touch.clientY - touchState.current.startY;

      touchState.current.currentX = touch.clientX;
      touchState.current.currentY = touch.clientY;

      const absX = Math.abs(deltaX);
      const absY = Math.abs(deltaY);

      // Determine if this is a horizontal or vertical gesture
      if (mergedConfig.direction === 'horizontal' && absX > absY && absX > 10) {
        // Prevent vertical scrolling during horizontal swipe
        e.preventDefault();

        const direction = deltaX > 0 ? 'right' : 'left';
        const progress = Math.min(absX / (mergedConfig.threshold * 2), 1);

        startGesture(direction);
        updateGesture(progress);

        // Haptic feedback at threshold
        if (absX >= mergedConfig.threshold && absX < mergedConfig.threshold + 5) {
          haptic.light();
        }
      } else if (mergedConfig.direction === 'vertical' && absY > absX && absY > 10) {
        // Pull-to-refresh gesture (only when pulling down)
        if (deltaY > 0 && handlers.onPullDown) {
          e.preventDefault();
          const progress = Math.min(deltaY / (mergedConfig.threshold * 2), 1);
          handlers.onPullDown(progress);

          // Haptic at threshold
          if (deltaY >= mergedConfig.threshold && deltaY < mergedConfig.threshold + 5) {
            haptic.light();
          }
        }
      }
    },
    [mergedConfig, startGesture, updateGesture, haptic, handlers]
  );

  const handleTouchEnd = useCallback(() => {
    if (!mergedConfig.enabled || !touchState.current.isTracking) return;

    const { startX, startY, startTime, currentX, currentY } = touchState.current;
    const deltaX = currentX - startX;
    const deltaY = currentY - startY;
    const deltaTime = Date.now() - startTime;
    const velocity = Math.abs(deltaX) / deltaTime;

    const absX = Math.abs(deltaX);
    const absY = Math.abs(deltaY);

    // Check if gesture meets threshold or velocity requirement
    const meetsThreshold = absX >= mergedConfig.threshold;
    const meetsVelocity = velocity >= mergedConfig.velocityThreshold;
    const shouldNavigate = meetsThreshold || meetsVelocity;

    if (mergedConfig.direction === 'horizontal' && absX > absY) {
      if (shouldNavigate) {
        haptic.medium();

        if (deltaX > 0 && handlers.onSwipeRight) {
          handlers.onSwipeRight();
        } else if (deltaX < 0 && handlers.onSwipeLeft) {
          handlers.onSwipeLeft();
        }
      }

      endGesture(shouldNavigate);
    } else if (mergedConfig.direction === 'vertical' && absY > absX) {
      if (deltaY > 0) {
        const shouldTrigger = absY >= mergedConfig.threshold;
        if (handlers.onPullRelease) {
          handlers.onPullRelease(shouldTrigger);
        }
        if (shouldTrigger) {
          haptic.medium();
        }
      } else if (deltaY < 0 && handlers.onSwipeUp) {
        if (absY >= mergedConfig.threshold) {
          haptic.medium();
          handlers.onSwipeUp();
        }
      }
    } else {
      cancelGesture();
    }

    touchState.current.isTracking = false;
  }, [mergedConfig, handlers, haptic, endGesture, cancelGesture]);

  const handleTouchCancel = useCallback(() => {
    touchState.current.isTracking = false;
    cancelGesture();
  }, [cancelGesture]);

  // Attach event listeners
  useEffect(() => {
    const element = elementRef.current;
    if (!element || !mergedConfig.enabled) return;

    element.addEventListener('touchstart', handleTouchStart, { passive: true });
    element.addEventListener('touchmove', handleTouchMove, { passive: false });
    element.addEventListener('touchend', handleTouchEnd, { passive: true });
    element.addEventListener('touchcancel', handleTouchCancel, { passive: true });

    return () => {
      element.removeEventListener('touchstart', handleTouchStart);
      element.removeEventListener('touchmove', handleTouchMove);
      element.removeEventListener('touchend', handleTouchEnd);
      element.removeEventListener('touchcancel', handleTouchCancel);
    };
  }, [elementRef, mergedConfig.enabled, handleTouchStart, handleTouchMove, handleTouchEnd, handleTouchCancel]);

  return {
    isTracking: touchState.current.isTracking,
  };
}

// Simplified hook for swipe navigation
export function useSwipeNavigation(
  elementRef: React.RefObject<HTMLElement | null>,
  config?: Omit<GestureConfig, 'direction'>
) {
  const { navigateLeft, navigateRight } = useViewStore();

  return useGesture(
    elementRef,
    {
      onSwipeLeft: navigateRight, // Swipe left = go to next view (right)
      onSwipeRight: navigateLeft, // Swipe right = go to previous view (left)
    },
    { ...config, direction: 'horizontal' }
  );
}

// Simplified hook for pull-to-refresh
export function usePullToRefresh(
  elementRef: React.RefObject<HTMLElement | null>,
  onRefresh: () => Promise<void>,
  config?: Omit<GestureConfig, 'direction'>
) {
  const { startPull, updatePull, triggerRefresh, endRefresh, isRefreshing } = useViewStore();

  const handlePullDown = useCallback(
    (progress: number) => {
      if (isRefreshing) return;
      startPull();
      updatePull(progress);
    },
    [isRefreshing, startPull, updatePull]
  );

  const handlePullRelease = useCallback(
    async (shouldTrigger: boolean) => {
      if (isRefreshing) return;

      if (shouldTrigger) {
        triggerRefresh();
        try {
          await onRefresh();
        } finally {
          endRefresh();
        }
      } else {
        endRefresh();
      }
    },
    [isRefreshing, triggerRefresh, onRefresh, endRefresh]
  );

  return useGesture(
    elementRef,
    {
      onPullDown: handlePullDown,
      onPullRelease: handlePullRelease,
    },
    { ...config, direction: 'vertical' }
  );
}
