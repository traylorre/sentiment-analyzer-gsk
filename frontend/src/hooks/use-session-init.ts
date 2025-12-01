'use client';

import { useEffect, useRef } from 'react';
import { useAuthStore } from '@/stores/auth-store';

/**
 * Hook for automatic session initialization on app load (Feature 014, FR-003).
 *
 * This hook ensures:
 * 1. Anonymous session is created automatically on first app load
 * 2. Existing valid sessions are reused from localStorage
 * 3. Session is initialized only once per app lifecycle
 * 4. Cross-tab session sharing via localStorage (zustand persist)
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
  const initAttempted = useRef(false);

  const {
    isAuthenticated,
    isInitialized,
    isLoading,
    error,
    isSessionValid,
    signInAnonymous,
    setInitialized,
    setError,
  } = useAuthStore();

  useEffect(() => {
    // Only run once per app lifecycle
    if (initAttempted.current || isInitialized) {
      return;
    }

    initAttempted.current = true;

    const initializeSession = async () => {
      try {
        // Check if we have a valid session from localStorage (zustand persist)
        if (isAuthenticated && isSessionValid()) {
          // Session restored from localStorage - no API call needed
          setInitialized(true);
          return;
        }

        // No valid session - create anonymous session
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
    isAuthenticated,
    isInitialized,
    isSessionValid,
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
