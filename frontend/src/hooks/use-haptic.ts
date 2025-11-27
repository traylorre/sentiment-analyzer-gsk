'use client';

import { useCallback, useMemo } from 'react';
import { haptic, type HapticIntensity } from '@/lib/utils/haptics';
import { useReducedMotion } from './use-reduced-motion';

interface UseHapticReturn {
  light: () => void;
  medium: () => void;
  heavy: () => void;
  selection: () => void;
  trigger: (intensity: HapticIntensity) => void;
  isEnabled: boolean;
}

/**
 * Hook for haptic feedback with reduced motion support
 * Returns no-op functions when user prefers reduced motion
 */
export function useHaptic(): UseHapticReturn {
  const prefersReducedMotion = useReducedMotion();

  const noop = useCallback(() => {}, []);

  const trigger = useCallback(
    (intensity: HapticIntensity) => {
      if (prefersReducedMotion) return;
      haptic[intensity]();
    },
    [prefersReducedMotion]
  );

  const light = useCallback(() => trigger('light'), [trigger]);
  const medium = useCallback(() => trigger('medium'), [trigger]);
  const heavy = useCallback(() => trigger('heavy'), [trigger]);
  const selection = useCallback(() => trigger('selection'), [trigger]);

  return useMemo(
    () =>
      prefersReducedMotion
        ? {
            light: noop,
            medium: noop,
            heavy: noop,
            selection: noop,
            trigger: noop,
            isEnabled: false,
          }
        : {
            light,
            medium,
            heavy,
            selection,
            trigger,
            isEnabled: haptic.isSupported(),
          },
    [prefersReducedMotion, light, medium, heavy, selection, trigger, noop]
  );
}
