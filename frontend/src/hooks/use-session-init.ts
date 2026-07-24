'use client';

import { useEffect } from 'react';
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
  const {
    isInitialized,
    isLoading,
    error,
    initializeSession,
    setInitialized,
    setError,
  } = useAuthStore();

  // Feature 1165: Initialize immediately - no hydration wait needed
  // Session restoration happens via httpOnly cookies, not localStorage
  useEffect(() => {
    // Feature 1384: bootstrap runs exactly once. The guard against duplicate
    // work now lives in the store's single-flight initializeSession() — shared
    // across every SessionProvider mount — instead of a per-component ref, which
    // could not stop two mounts from both minting an anonymous session and
    // clobbering the OAuth refresh cookie. When already initialized, skip.
    if (isInitialized) {
      return;
    }

    // Clear stale OAuth sessionStorage keys from previous auth attempts.
    // CRITICAL: skip on /auth/callback. SessionProvider (root layout) runs this
    // on every page, and useSearchParams' Suspense boundary defers the callback
    // page's own effect — so without this guard we wipe oauth_provider/oauth_state
    // before the callback can read them, making every OAuth sign-in fail with
    // "Authentication session expired" (the callback clears them itself after use).
    if (!window.location.pathname.startsWith('/auth/callback')) {
      sessionStorage.removeItem('oauth_provider');
      sessionStorage.removeItem('oauth_state');
    }

    const run = async () => {
      try {
        // Feature 1384: restore-first, single-flight bootstrap owned by the
        // store. initializeSession() restores from the httpOnly refresh cookie
        // (guest OR OAuth) and only mints a NEW anonymous user when nothing is
        // restorable. Raced against a timeout so a hung network call cannot
        // leave the UI stuck on "Initializing session…".
        await Promise.race([
          initializeSession(),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error('timeout')), SESSION_INIT_TIMEOUT_MS)
          ),
        ]);
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

    run();
  }, [
    isInitialized,
    initializeSession,
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
