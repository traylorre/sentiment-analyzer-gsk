'use client';

/**
 * Auth Hook - Provides authentication state and actions.
 *
 * Feature 1165: Removed hydration dependencies.
 * Auth state now initializes immediately (memory-only store).
 */

import { useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';
import type { OAuthProvider } from '@/types/auth';

// Session refresh interval (5 minutes before expiry)
const REFRESH_BUFFER_MS = 5 * 60 * 1000;
// Check interval for session validity
const CHECK_INTERVAL_MS = 60 * 1000;

interface UseAuthOptions {
  redirectTo?: string;
  requireAuth?: boolean;
}

export function useAuth(options: UseAuthOptions = {}) {
  const { redirectTo = '/auth/signin', requireAuth = false } = options;
  const router = useRouter();
  const refreshTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const {
    user,
    tokens,
    isAuthenticated,
    isAnonymous,
    isLoading,
    isInitialized,
    error,
    sessionExpiresAt,
    signInAnonymous,
    signInWithMagicLink,
    verifyMagicLink,
    signInWithOAuth,
    handleOAuthCallback,
    refreshSession,
    signOut,
    isSessionValid,
    getSessionRemainingMs,
    setInitialized,
  } = useAuthStore();

  // Initialize auth state - Feature 1165: No hydration wait needed
  useEffect(() => {
    if (!isInitialized) {
      // Check if there's a valid session
      const hasValidSession = isAuthenticated && isSessionValid();

      if (!hasValidSession && requireAuth) {
        // Try anonymous auth if no session
        signInAnonymous().catch((error) => {
          // Log the error for debugging - silent failures are hard to diagnose
          console.error('[useAuth] Anonymous sign-in failed:', error);
          // If anonymous fails and auth is required, redirect
          router.push(redirectTo);
        });
      }

      setInitialized(true);
    }
  }, [isInitialized, isAuthenticated, requireAuth, redirectTo, router, signInAnonymous, setInitialized, isSessionValid]);

  // Schedule session refresh
  useEffect(() => {
    if (!isAuthenticated || !sessionExpiresAt) {
      return;
    }

    const scheduleRefresh = () => {
      const remainingMs = getSessionRemainingMs();

      if (remainingMs <= 0) {
        // Session expired
        signOut();
        if (requireAuth) {
          router.push(redirectTo);
        }
        return;
      }

      // Schedule refresh before expiry
      const refreshIn = Math.max(0, remainingMs - REFRESH_BUFFER_MS);

      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current);
      }

      refreshTimeoutRef.current = setTimeout(() => {
        refreshSession();
      }, refreshIn);
    };

    scheduleRefresh();

    // Also check periodically
    const checkInterval = setInterval(() => {
      if (!isSessionValid()) {
        signOut();
        if (requireAuth) {
          router.push(redirectTo);
        }
      }
    }, CHECK_INTERVAL_MS);

    return () => {
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current);
      }
      clearInterval(checkInterval);
    };
  }, [
    isAuthenticated,
    sessionExpiresAt,
    requireAuth,
    redirectTo,
    router,
    getSessionRemainingMs,
    isSessionValid,
    refreshSession,
    signOut,
  ]);

  // Redirect if auth required but not authenticated
  useEffect(() => {
    if (isInitialized && requireAuth && !isAuthenticated && !isLoading) {
      router.push(redirectTo);
    }
  }, [isInitialized, requireAuth, isAuthenticated, isLoading, redirectTo, router]);

  // Sign in with magic link
  const requestMagicLink = useCallback(
    async (email: string, captchaToken: string) => {
      await signInWithMagicLink(email, captchaToken);
    },
    [signInWithMagicLink]
  );

  // Verify magic link token
  const verifyToken = useCallback(
    async (token: string) => {
      await verifyMagicLink(token);
      router.push('/');
    },
    [verifyMagicLink, router]
  );

  // OAuth sign in
  const signInOAuth = useCallback(
    async (provider: OAuthProvider) => {
      await signInWithOAuth(provider);
    },
    [signInWithOAuth]
  );

  // Handle OAuth callback
  // Feature 1193: Accepts state and redirectUri for CSRF validation
  const handleCallback = useCallback(
    async (code: string, provider: OAuthProvider, state: string, redirectUri: string) => {
      await handleOAuthCallback(code, provider, state, redirectUri);
      router.push('/');
    },
    [handleOAuthCallback, router]
  );

  // Sign out
  const handleSignOut = useCallback(async () => {
    await signOut();
    router.push(redirectTo);
  }, [signOut, router, redirectTo]);

  return {
    user,
    tokens,
    isAuthenticated,
    isAnonymous,
    isLoading,
    isInitialized,
    error,
    sessionExpiresAt,
    remainingSessionMs: getSessionRemainingMs(),
    isSessionValid: isSessionValid(),

    // Actions
    signInAnonymous,
    requestMagicLink,
    verifyToken,
    signInOAuth,
    handleCallback,
    refreshSession,
    signOut: handleSignOut,
  };
}

// Hook for checking if user has upgraded from anonymous
export function useIsUpgraded() {
  const { user } = useAuthStore();
  return user && user.authType !== 'anonymous';
}

// Hook for getting auth headers
export function useAuthHeaders() {
  const { tokens } = useAuthStore();

  if (!tokens?.accessToken) {
    return {};
  }

  return {
    Authorization: `Bearer ${tokens.accessToken}`,
  };
}
