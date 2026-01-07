'use client';

import { useEffect, useRef } from 'react';
import { useAuthStore } from '@/stores/auth-store';

/**
 * Hook for automatic session initialization on app load.
 *
 * Feature 1165: Simplified - no longer waits for localStorage hydration.
 * Session restoration relies on httpOnly cookies via /refresh endpoint.
 *
 * This hook ensures:
 * 1. Anonymous session is created automatically on first app load
 * 2. Session is initialized only once per app lifecycle
 * 3. Graceful error handling
 *
 * Usage:
 * ```tsx
 * function SessionProvider({ children }) {
 *   const { isInitializing, isError, error } = useSessionInit();
 *
 *   if (isInitializing) return <LoadingSpinner />;
 *   if (isError) return <ErrorBoundary error={error} />;
 *
 *   return <>{children}</>;
 * }
 * ```
 */
export function useSessionInit() {
  // Ref guard to prevent multiple init attempts from different renders
  const initAttempted = useRef(false);

  const {
    isInitialized,
    isLoading,
    error,
    signInAnonymous,
    setInitialized,
    setError,
  } = useAuthStore();

  // Feature 1165: Initialize immediately - no hydration wait needed
  // Session restoration happens via httpOnly cookies, not localStorage
  useEffect(() => {
    // Only run once per app lifecycle
    if (initAttempted.current || isInitialized) {
      return;
    }

    initAttempted.current = true;

    const initializeSession = async () => {
      try {
        // TODO: In future, call /refresh endpoint here to restore session from httpOnly cookie
        // For now, create anonymous session
        await signInAnonymous();
        setInitialized(true);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to initialize session';
        setError(message);
        // Still mark as initialized to prevent retry loops
        setInitialized(true);
      }
    };

    initializeSession();
  }, [
    isInitialized,
    signInAnonymous,
    setInitialized,
    setError,
  ]);

  return {
    isInitializing: !isInitialized || isLoading,
    isError: !!error,
    error,
    isReady: isInitialized && !isLoading && !error,
  };
}
