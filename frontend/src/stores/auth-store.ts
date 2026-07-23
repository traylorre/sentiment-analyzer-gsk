'use client';

/**
 * Auth Store - Memory-only state management for authentication.
 *
 * Feature 1165: Removed persist() middleware for security (CVSS 8.6).
 * Session restoration uses httpOnly cookies via /refresh endpoint.
 * No authentication data is stored in localStorage.
 */

import { create } from 'zustand';
import type { User, AuthTokens, AuthState, OAuthProvider } from '@/types/auth';
import { setUserId, setAccessToken, emitErrorEvent } from '@/lib/api/client';
import { authApi } from '@/lib/api/auth';

interface AuthStore extends AuthState {
  // Loading states
  isLoading: boolean;
  isInitialized: boolean;
  error: string | null;

  // Auth degradation tracking (User Story 3)
  refreshFailureCount: number;
  sessionDegraded: boolean;

  // Actions
  setUser: (user: User | null) => void;
  setTokens: (tokens: AuthTokens | null) => void;
  setSession: (expiresAt: string | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setInitialized: (initialized: boolean) => void;

  // Auth operations
  restoreSession: () => Promise<boolean>; // M1 WI-3: cookie-based restore at init
  signInAnonymous: () => Promise<void>;
  signInWithMagicLink: (email: string, token: string) => Promise<void>;
  verifyMagicLink: (token: string, sig?: string) => Promise<void>;
  signInWithOAuth: (provider: OAuthProvider) => Promise<void>;
  handleOAuthCallback: (
    code: string,
    provider: OAuthProvider,
    state: string,
    redirectUri: string
  ) => Promise<void>;
  refreshSession: () => Promise<void>;
  refreshUserProfile: () => Promise<void>; // Feature 1174: Refresh federation fields
  signOut: () => Promise<void>;

  // Session helpers
  isSessionValid: () => boolean;
  getSessionRemainingMs: () => number;

  // Reset
  reset: () => void;
}

const initialState: AuthState & { isLoading: boolean; isInitialized: boolean; error: string | null; refreshFailureCount: number; sessionDegraded: boolean } = {
  isAuthenticated: false,
  isAnonymous: false,
  user: null,
  tokens: null,
  sessionExpiresAt: null,
  isLoading: false,
  isInitialized: false,
  error: null,
  refreshFailureCount: 0,
  sessionDegraded: false,
};

// Feature 1165: Memory-only store - no persist() middleware
// Session restoration relies on httpOnly cookies via /refresh endpoint
export const useAuthStore = create<AuthStore>((set, get) => ({
  ...initialState,

  setUser: (user) => {
    const isAnonymous = user?.authType === 'anonymous';
    set({
      user,
      isAuthenticated: !!user,
      isAnonymous,
    });
    // Feature 1146: setUserId now also sets accessToken for Bearer auth
    // This ensures anonymous sessions use Bearer token, not X-User-ID header
    setUserId(user?.userId ?? null);
  },

  setTokens: (tokens) => {
    set({ tokens });
    // Feature 014: Sync accessToken with API client for Bearer header
    setAccessToken(tokens?.accessToken ?? null);
  },

  setSession: (expiresAt) => set({ sessionExpiresAt: expiresAt }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),

  setInitialized: (initialized) => set({ isInitialized: initialized }),

  restoreSession: async () => {
    // M1 WI-3: restore the previous session from the httpOnly refresh cookie
    // instead of minting a new anonymous user on every reload. Returns true
    // when a session was restored; false means the caller should fall back
    // to signInAnonymous(). Never throws.
    const { setUser, setSession, setTokens } = get();

    try {
      const data = await authApi.refreshToken();

      if (!data.accessToken) {
        return false;
      }

      if (data.authType === 'anonymous' && data.userId) {
        // Guest restore: bearer token IS the user_id; rebuild minimal user
        // state exactly as signInAnonymous does.
        setUser({
          userId: data.userId,
          authType: 'anonymous',
          createdAt: '',
          configurationCount: 0,
          alertCount: 0,
          emailNotificationsEnabled: false,
          role: 'anonymous',
          linkedProviders: [],
          verification: 'none',
          lastProviderUsed: undefined,
        });
        setTokens({
          accessToken: data.accessToken,
          refreshToken: '', // stays in the httpOnly cookie
          idToken: '',
          expiresIn: data.expiresIn,
        });
        setSession(data.sessionExpiresAt);
        return true;
      }

      // Cognito-backed restore (OAuth session): tokens first, then rebuild
      // the profile from /auth/me using the fresh bearer.
      setTokens({
        accessToken: data.accessToken,
        refreshToken: '', // stays in the httpOnly cookie
        idToken: data.idToken ?? '',
        expiresIn: data.expiresIn,
      });
      try {
        const profile = await authApi.getProfile();
        if (profile.userId) {
          setUser({
            userId: profile.userId,
            authType: profile.authType ?? 'email',
            createdAt: profile.createdAt ?? '',
            configurationCount: profile.configurationCount ?? 0,
            alertCount: profile.alertCount ?? 0,
            emailNotificationsEnabled:
              profile.emailNotificationsEnabled ?? false,
            role: profile.role ?? 'free',
            linkedProviders: profile.linkedProviders ?? [],
            verification: profile.verification ?? 'none',
            lastProviderUsed: profile.lastProviderUsed,
            email: profile.email,
          });
        }
      } catch {
        // Profile rebuild is best-effort; the session itself is restored.
      }
      return true;
    } catch {
      // 401 (no/invalid cookie) or network failure: not restorable.
      return false;
    }
  },

  signInAnonymous: async () => {
    const { setLoading, setError, setUser, setSession, setTokens } = get();

    try {
      setLoading(true);
      setError(null);

      // Use authApi with proper snake_case → camelCase mapping
      // Per spec: specs/006-user-config-dashboard/contracts/auth-api.md
      const data = await authApi.createAnonymousSession();

      setUser({
        userId: data.userId,
        authType: 'anonymous',
        createdAt: data.createdAt,
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: false,
        // Feature 1174: Federation field defaults for anonymous users
        role: 'anonymous',
        linkedProviders: [],
        verification: 'none',
        lastProviderUsed: undefined,
      });
      // Set tokens so useChartData's hasAccessToken check passes
      // For anonymous sessions, token === userId (no refresh token or id token)
      setTokens({
        accessToken: data.token,
        refreshToken: '',  // Empty string for anonymous (no refresh)
        idToken: '',       // Empty string for anonymous (no id token)
        expiresIn: 0,      // Session expiry handled separately
      });
      setSession(data.sessionExpiresAt);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unknown error');
      throw error;
    } finally {
      setLoading(false);
    }
  },

  signInWithMagicLink: async (email: string, _captchaToken: string) => {
    const { setLoading, setError } = get();

    try {
      setLoading(true);
      setError(null);

      // Use authApi to route to Lambda backend
      await authApi.requestMagicLink(email);

      // Magic link sent successfully - user needs to check email
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unknown error');
      throw error;
    } finally {
      setLoading(false);
    }
  },

  verifyMagicLink: async (token: string, sig?: string) => {
    const { setLoading, setError, setUser, setTokens, setSession } = get();

    try {
      setLoading(true);
      setError(null);

      // Use authApi to route to Lambda backend
      // Note: sig should be extracted from URL params by the caller
      const data = await authApi.verifyMagicLink(token, sig ?? '');

      setUser(data.user);
      setTokens(data.tokens);
      // Calculate session expiry from expiresIn (seconds)
      const expiresAt = new Date(Date.now() + data.tokens.expiresIn * 1000).toISOString();
      setSession(expiresAt);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unknown error');
      throw error;
    } finally {
      setLoading(false);
    }
  },

  signInWithOAuth: async (provider: OAuthProvider) => {
    const { setLoading, setError } = get();

    try {
      setLoading(true);
      setError(null);

      // Use authApi to route to Lambda backend
      const urls = await authApi.getOAuthUrls();
      const providerInfo = urls.providers[provider];

      // Feature 1192: Store provider for callback page retrieval
      // Feature 1193: Store state for CSRF validation
      // sessionStorage chosen for cross-tab isolation (each tab has own OAuth flow)
      sessionStorage.setItem('oauth_provider', provider);
      sessionStorage.setItem('oauth_state', providerInfo.state);

      // Feature 1192: Store provider for callback page retrieval
      // sessionStorage chosen for cross-tab isolation (each tab has own OAuth flow)
      sessionStorage.setItem('oauth_provider', provider);

      // Redirect to OAuth provider
      window.location.href = providerInfo.authorize_url;
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unknown error');
      setLoading(false);
      throw error;
    }
  },

  handleOAuthCallback: async (
    code: string,
    provider: OAuthProvider,
    state: string,
    redirectUri: string
  ) => {
    const { setLoading, setError, setUser, setTokens, setSession } = get();

    try {
      setLoading(true);
      setError(null);

      // Use authApi to route to Lambda backend
      // Feature 1193: Send state and redirect_uri for CSRF validation
      const data = await authApi.exchangeOAuthCode(provider, code, state, redirectUri);

      setUser(data.user);
      setTokens(data.tokens);
      // Calculate session expiry from expiresIn (seconds)
      const expiresAt = new Date(Date.now() + data.tokens.expiresIn * 1000).toISOString();
      setSession(expiresAt);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unknown error');
      throw error;
    } finally {
      setLoading(false);
    }
  },

  refreshSession: async () => {
    const { tokens, setTokens, setError } = get();

    if (!tokens?.refreshToken) {
      return;
    }

    try {
      // Use authApi to route to Lambda backend
      // Feature 1168: Refresh token now sent via httpOnly cookie, not in request body
      const data = await authApi.refreshToken();

      // M1 WI-3: the unmapped client used to yield accessToken === undefined
      // here silently; a refresh without an access token is now an explicit
      // failure that feeds the degradation counter.
      if (!data.accessToken) {
        throw new Error('Refresh returned no access token');
      }

      // Update tokens with new access token (preserving refresh token)
      setTokens({
        ...tokens,
        accessToken: data.accessToken,
        idToken: data.idToken ?? tokens.idToken ?? '',
      });
      // User Story 3: Reset degradation state on successful refresh
      set({ refreshFailureCount: 0, sessionDegraded: false });
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unknown error');
      // User Story 3: Track consecutive refresh failures for degradation detection
      const count = get().refreshFailureCount + 1;
      set({ refreshFailureCount: count });
      if (count >= 2) {
        set({ sessionDegraded: true });
        emitErrorEvent('auth_degradation_warning', { failureCount: count });
      }
      // Don't throw - let the session expire gracefully
    }
  },

  /**
   * Refresh user profile to get updated federation fields.
   * Feature 1174: Fetches /api/v2/auth/me and merges federation data into user state.
   */
  refreshUserProfile: async () => {
    const { user, setUser, setError } = get();

    if (!user) {
      return;
    }

    try {
      const profileData = await authApi.getProfile();
      // Merge new profile data with existing user (preserving userId, createdAt, etc.)
      setUser({
        ...user,
        ...profileData,
      });
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unknown error');
      // FR-006: Observability for profile refresh failures
      console.warn('[authStore] Profile refresh failed:', error instanceof Error ? error.message : 'Unknown error');
      // Don't throw - profile refresh is non-critical
    }
  },

  signOut: async () => {
    const { tokens, reset } = get();

    try {
      if (tokens?.accessToken) {
        // Use authApi to route to Lambda backend
        // authApi automatically handles Authorization header
        await authApi.signOut();
      }
    } catch (error) {
      // Log sign-out errors for debugging - backend session may remain active
      console.error('[authStore.signOut] Failed to sign out from backend:', error);
      // Still clear local state to prevent UI lockout, but backend token may persist
      // This is a known trade-off: prioritize user experience over perfect cleanup
    } finally {
      reset();
    }
  },

  isSessionValid: () => {
    const { sessionExpiresAt, isAuthenticated } = get();

    if (!isAuthenticated || !sessionExpiresAt) {
      return false;
    }

    return new Date(sessionExpiresAt).getTime() > Date.now();
  },

  getSessionRemainingMs: () => {
    const { sessionExpiresAt } = get();

    if (!sessionExpiresAt) {
      return 0;
    }

    const remaining = new Date(sessionExpiresAt).getTime() - Date.now();
    return Math.max(0, remaining);
  },

  reset: () => {
    // Feature 014: Clear API client auth state
    setUserId(null);
    setAccessToken(null);
    set(initialState);
  },
}));

// Selector hooks for common use cases
export const useUser = () => useAuthStore((state) => state.user);
export const useIsAuthenticated = () => useAuthStore((state) => state.isAuthenticated);
export const useIsAnonymous = () => useAuthStore((state) => state.isAnonymous);
export const useAuthLoading = () => useAuthStore((state) => state.isLoading);
export const useAuthError = () => useAuthStore((state) => state.error);

// Feature 1191: Subscription selector hooks
export const useUserRole = () => useAuthStore((state) => state.user?.role);
export const useIsSubscriptionActive = () =>
  useAuthStore((state) => state.user?.subscriptionActive ?? false);
export const useSubscriptionExpiresAt = () =>
  useAuthStore((state) => state.user?.subscriptionExpiresAt);
