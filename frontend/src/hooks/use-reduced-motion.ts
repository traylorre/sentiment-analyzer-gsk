'use client';

import { useSyncExternalStore } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';

function subscribe(onChange: () => void) {
  const mediaQuery = window.matchMedia(QUERY);
  mediaQuery.addEventListener('change', onChange);
  return () => mediaQuery.removeEventListener('change', onChange);
}

const getSnapshot = () => window.matchMedia(QUERY).matches;

const getServerSnapshot = () => false;

/**
 * Hook to detect if the user prefers reduced motion
 * Returns true if the user has requested reduced motion in their OS settings
 */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
