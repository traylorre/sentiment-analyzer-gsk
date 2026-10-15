'use client';

import { type ReactNode, useSyncExternalStore } from 'react';

/**
 * Test-only error trigger wrapper (Feature 1265, fixed in 1275).
 *
 * When `window.__TEST_FORCE_ERROR` is set to `true`, this component throws
 * during render, which is caught by the nearest React ErrorBoundary.
 *
 * SSR-safe: the flag is read through useSyncExternalStore with a server
 * snapshot of false, so SSR and hydration render children and match the
 * server HTML; React then re-renders with the client snapshot, which throws.
 *
 * Production-stripped: Only active when NODE_ENV !== 'production'.
 * In production builds, ErrorTriggerInner is tree-shaken away.
 */

declare global {
  interface Window {
    __TEST_FORCE_ERROR?: boolean;
  }
}

interface ErrorTriggerProps {
  children: ReactNode;
}

// The flag is set once by the E2E harness before the app loads; nothing to subscribe to.
const subscribe = () => () => {};
const getSnapshot = () => window.__TEST_FORCE_ERROR === true;
const getServerSnapshot = () => false;

/**
 * Inner component that uses hooks for SSR-safe error detection.
 * Separated from the outer ErrorTrigger to avoid conditional hook calls
 * (Rules of Hooks: hooks must be called unconditionally).
 */
function ErrorTriggerInner({ children }: ErrorTriggerProps) {
  const shouldError = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  if (shouldError) {
    throw new Error('TEST_FORCE_ERROR: Intentional error triggered by E2E test');
  }

  return <>{children}</>;
}

/**
 * Outer wrapper: production passthrough, non-production delegates to inner.
 * No hooks here — safe to early-return in production.
 */
export function ErrorTrigger({ children }: ErrorTriggerProps) {
  // In production, this is a transparent passthrough (zero overhead).
  // Tree shaking eliminates ErrorTriggerInner from the production bundle.
  if (process.env.NODE_ENV === 'production') {
    return <>{children}</>;
  }

  return <ErrorTriggerInner>{children}</ErrorTriggerInner>;
}
