'use client';

import { useEffect, useRef, useState } from 'react';
import { useAuthStore, useHasHydrated } from '@/stores/auth-store';

// FR-006: Hydration timeout - if zustand persist doesn't rehydrate within 5 seconds,
// proceed with empty state (graceful degradation)
const HYDRATION_TIMEOUT_MS = 5000;

/**
 * Hook for automatic session initialization on app load (Feature 014, FR-003).
 *
 * FR-016: This hook now waits for zustand persist rehydration before checking auth state.
 *
 * This hook ensures:
 * 1. WAITS for zustand persist to rehydrate from localStorage (FR-013)
 * 2. Anonymous session is created automatically on first app load (if no valid session)
 * 3. Existing valid sessions are reused from localStorage (no API call)
 * 4. Session is initialized only once per app lifecycle
 * 5. Cross-tab session sharing via localStorage (zustand persist)
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
  // T012: Ref guard to prevent multiple init attempts from different renders
  const initAttempted = useRef(false);
  // Track if hydration timed out
  const [hydrationTimedOut, setHydrationTimedOut] = useState(false);

  // FR-013: Check if zustand persist has completed rehydration
  const hasHydrated = useHasHydrated();

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

  // FR-006: Hydration timeout - proceed with empty state if rehydration takes too long
  useEffect(() => {
    if (hasHydrated) return; // Already hydrated, no need for timeout

    const timeoutId = setTimeout(() => {
      if (!useAuthStore.getState()._hasHydrated) {
        console.warn('[useSessionInit] Hydration timeout - proceeding with empty state');
        setHydrationTimedOut(true);
      }
    }, HYDRATION_TIMEOUT_MS);

    return () => clearTimeout(timeoutId);
  }, [hasHydrated]);

  // T010-T011: Main initialization effect - only runs AFTER hydration completes
  useEffect(() => {
    // Wait for zustand persist to rehydrate OR timeout
    if (!hasHydrated && !hydrationTimedOut) {
      return;
    }

    // Only run once per app lifecycle
    if (initAttempted.current || isInitialized) {
      return;
    }

    initAttempted.current = true;

    const initializeSession = async () => {
      try {
        // Check if we have a valid session from localStorage (zustand persist)
        // This check now happens AFTER hydration, so we have the real state
        if (isAuthenticated && isSessionValid()) {
          // Session restored from localStorage - no API call needed (US2)
          setInitialized(true);
          return;
        }

        // No valid session (or expired session - US3) - create anonymous session
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
    hasHydrated,
    hydrationTimedOut,
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
