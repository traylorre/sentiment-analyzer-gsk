'use client';

import { type ReactNode, useState, useEffect } from 'react';

/**
 * Test-only error trigger wrapper (Feature 1265, fixed in 1275).
 *
 * When `window.__TEST_FORCE_ERROR` is set to `true`, this component throws
 * during render, which is caught by the nearest React ErrorBoundary.
 *
 * SSR-safe: Uses useEffect to detect the flag after hydration, avoiding
 * hydration mismatches. The flag check cannot happen during SSR (no window)
 * or during hydration (must match server HTML). Instead, useEffect fires
 * after mount, sets state, and the subsequent re-render throws.
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

/**
 * Inner component that uses hooks for SSR-safe error detection.
 * Separated from the outer ErrorTrigger to avoid conditional hook calls
 * (Rules of Hooks: hooks must be called unconditionally).
 */
function ErrorTriggerInner({ children }: ErrorTriggerProps) {
  const [shouldError, setShouldError] = useState(false);

  // Check the flag after mount (post-hydration). This avoids the SSR/hydration
  // mismatch: server renders children, hydration matches, then this effect fires
  // and triggers a clean re-render that throws.
  useEffect(() => {
    if (typeof window !== 'undefined' && window.__TEST_FORCE_ERROR) {
      setShouldError(true);
    }
  }, []);

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
