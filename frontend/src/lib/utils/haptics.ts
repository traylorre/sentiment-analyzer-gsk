/**
 * Haptic feedback utilities
 * Uses the Vibration API with graceful degradation
 */

export type HapticIntensity = 'light' | 'medium' | 'heavy' | 'selection';

const HAPTIC_PATTERNS: Record<HapticIntensity, number | number[]> = {
  light: 10,
  medium: 20,
  heavy: 30,
  selection: [5, 10, 5],
};

/**
 * Trigger haptic feedback if available
 */
export function triggerHaptic(intensity: HapticIntensity = 'light'): boolean {
  if (typeof navigator === 'undefined' || !navigator.vibrate) {
    return false;
  }

  try {
    return navigator.vibrate(HAPTIC_PATTERNS[intensity]);
  } catch {
    return false;
  }
}

/**
 * Check if haptic feedback is supported
 */
export function isHapticSupported(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function';
}

/**
 * Convenience methods for haptic feedback
 */
export const haptic = {
  light: () => triggerHaptic('light'),
  medium: () => triggerHaptic('medium'),
  heavy: () => triggerHaptic('heavy'),
  selection: () => triggerHaptic('selection'),
  isSupported: isHapticSupported,
} as const;
