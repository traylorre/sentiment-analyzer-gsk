'use client';

import { type ReactNode } from 'react';

/**
 * Test-only error trigger wrapper (Feature 1265).
 *
 * When `window.__TEST_FORCE_ERROR` is set to `true`, this component throws
 * during render, which is caught by the nearest React ErrorBoundary.
 *
 * Production-stripped: Only active when NODE_ENV !== 'production'.
 * In production builds, this is a transparent passthrough.
 */

declare global {
  interface Window {
    __TEST_FORCE_ERROR?: boolean;
  }
}

interface ErrorTriggerProps {
  children: ReactNode;
}

export function ErrorTrigger({ children }: ErrorTriggerProps) {
  // In production, this is a transparent passthrough
  if (process.env.NODE_ENV === 'production') {
    return <>{children}</>;
  }

  // In dev/test, check the global flag during render
  if (typeof window !== 'undefined' && window.__TEST_FORCE_ERROR) {
    throw new Error('TEST_FORCE_ERROR: Intentional error triggered by E2E test');
  }

  return <>{children}</>;
}
