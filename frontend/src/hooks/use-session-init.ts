'use client';

import { useEffect, useRef } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { SESSION_INIT_TIMEOUT_MS } from '@/lib/constants';

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

    // Clear stale OAuth sessionStorage keys from previous auth attempts
    sessionStorage.removeItem('oauth_provider');
    sessionStorage.removeItem('oauth_state');

    const initializeSession = async () => {
      try {
        // TODO: In future, call /refresh endpoint here to restore session from httpOnly cookie
        // For now, create anonymous session with timeout protection
        await Promise.race([
          signInAnonymous(),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error('timeout')), SESSION_INIT_TIMEOUT_MS)
          ),
        ]);
        setInitialized(true);
      } catch (err) {
        if (err instanceof Error && err.message === 'timeout') {
          setError('Session initialization timed out. Please refresh.');
          setInitialized(true);
          return;
        }
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
    // Bug fix: Only show initializing during actual session init, NOT during
    // subsequent auth operations (verify, refresh, OAuth callback). The shared
    // isLoading flag from auth store was causing SessionProvider to re-show
    // "Initializing session..." when other auth actions set isLoading=true.
    isInitializing: !isInitialized,
    isError: !!error,
    error,
    isReady: isInitialized && !isLoading && !error,
  };
}
