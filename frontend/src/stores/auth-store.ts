'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { User, AuthTokens, AuthState, OAuthProvider } from '@/types/auth';
import { setUserId, setAccessToken } from '@/lib/api/client';
import { authApi } from '@/lib/api/auth';

interface AuthStore extends AuthState {
  // Hydration state (FR-013: zustand persist rehydration tracking)
  _hasHydrated: boolean;

  // Loading states
  isLoading: boolean;
  isInitialized: boolean;
  error: string | null;

  // Actions
  setUser: (user: User | null) => void;
  setTokens: (tokens: AuthTokens | null) => void;
  setSession: (expiresAt: string | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setInitialized: (initialized: boolean) => void;

  // Auth operations
  signInAnonymous: () => Promise<void>;
  signInWithMagicLink: (email: string, token: string) => Promise<void>;
  verifyMagicLink: (token: string, sig?: string) => Promise<void>;
  signInWithOAuth: (provider: OAuthProvider) => Promise<void>;
  handleOAuthCallback: (code: string, provider: OAuthProvider) => Promise<void>;
  refreshSession: () => Promise<void>;
  signOut: () => Promise<void>;

  // Session helpers
  isSessionValid: () => boolean;
  getSessionRemainingMs: () => number;

  // Reset
  reset: () => void;
}

const initialState: AuthState & { _hasHydrated: boolean; isLoading: boolean; isInitialized: boolean; error: string | null } = {
  isAuthenticated: false,
  isAnonymous: false,
  user: null,
  tokens: null,
  sessionExpiresAt: null,
  _hasHydrated: false, // FR-013: false until onRehydrateStorage fires
  isLoading: false,
  isInitialized: false,
  error: null,
};

// Token storage key
const TOKEN_STORAGE_KEY = 'sentiment-auth-tokens';

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      ...initialState,

      setUser: (user) => {
        const isAnonymous = user?.authType === 'anonymous';
        set({
          user,
          isAuthenticated: !!user,
          isAnonymous,
        });
        // Feature 014: Sync userId with API client for X-User-ID header
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

      signInAnonymous: async () => {
        const { setLoading, setError, setUser, setSession } = get();

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

          // Redirect to OAuth provider
          window.location.href = urls[provider];
        } catch (error) {
          setError(error instanceof Error ? error.message : 'Unknown error');
          setLoading(false);
          throw error;
        }
      },

      handleOAuthCallback: async (code: string, provider: OAuthProvider) => {
        const { setLoading, setError, setUser, setTokens, setSession } = get();

        try {
          setLoading(true);
          setError(null);

          // Use authApi to route to Lambda backend
          const data = await authApi.exchangeOAuthCode(provider, code);

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
          const data = await authApi.refreshToken(tokens.refreshToken);

          // Update tokens with new access token (preserving refresh token)
          setTokens({
            ...tokens,
            accessToken: data.accessToken,
            idToken: data.idToken,
          });
        } catch (error) {
          setError(error instanceof Error ? error.message : 'Unknown error');
          // Don't throw - let the session expire gracefully
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
        } catch {
          // Ignore logout errors - still clear local state
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
    }),
    {
      name: TOKEN_STORAGE_KEY,
      // T037: Graceful fallback for localStorage unavailable (FR-004)
      // createJSONStorage handles errors internally, but we wrap for extra safety
      storage: createJSONStorage(() => {
        // Check if localStorage is available (may not be in private browsing)
        if (typeof window === 'undefined') {
          // SSR - return a no-op storage
          return {
            getItem: () => null,
            setItem: () => {},
            removeItem: () => {},
          };
        }
        try {
          // Test localStorage availability
          const testKey = '__storage_test__';
          window.localStorage.setItem(testKey, testKey);
          window.localStorage.removeItem(testKey);
          return window.localStorage;
        } catch {
          // localStorage not available (private browsing, quota exceeded)
          console.warn('[auth-store] localStorage unavailable, using in-memory storage');
          // Return a simple in-memory storage fallback
          const memoryStorage: Record<string, string> = {};
          return {
            getItem: (key: string) => memoryStorage[key] ?? null,
            setItem: (key: string, value: string) => { memoryStorage[key] = value; },
            removeItem: (key: string) => { delete memoryStorage[key]; },
          };
        }
      }),
      // FR-013: Exclude _hasHydrated from persistence - it's runtime-only state
      // Feature 1131: Security fix - tokens MUST NOT be persisted to localStorage (CVSS 8.6)
      // Tokens remain in-memory only to prevent XSS attacks from stealing credentials
      partialize: (state) => ({
        user: state.user,
        // SECURITY: tokens intentionally excluded - stored in memory only
        sessionExpiresAt: state.sessionExpiresAt,
        isAuthenticated: state.isAuthenticated,
        isAnonymous: state.isAnonymous,
        // Note: _hasHydrated, isLoading, isInitialized, error, tokens are NOT persisted
      }),
      // FR-013: Set _hasHydrated to true after zustand persist rehydrates from localStorage
      // Feature 1131: Also perform one-time migration to clear any existing tokens
      onRehydrateStorage: () => (state) => {
        // This callback fires AFTER rehydration completes (success or failure)
        // state will be undefined if rehydration failed

        // Feature 1131: Migration - clear any existing tokens from localStorage
        // This handles users who authenticated before the security fix
        if (typeof window !== 'undefined') {
          try {
            const stored = window.localStorage.getItem(TOKEN_STORAGE_KEY);
            if (stored) {
              const parsed = JSON.parse(stored);
              if (parsed.state?.tokens) {
                delete parsed.state.tokens;
                window.localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(parsed));
              }
            }
          } catch {
            // Ignore parse errors - localStorage may be corrupted or unavailable
          }
        }

        useAuthStore.setState({ _hasHydrated: true });
      },
    }
  )
);

// Selector hooks for common use cases
export const useUser = () => useAuthStore((state) => state.user);
export const useIsAuthenticated = () => useAuthStore((state) => state.isAuthenticated);
export const useIsAnonymous = () => useAuthStore((state) => state.isAnonymous);
export const useAuthLoading = () => useAuthStore((state) => state.isLoading);
export const useAuthError = () => useAuthStore((state) => state.error);

// FR-013: Hydration state selector for components to check before reading auth state
export const useHasHydrated = () => useAuthStore((state) => state._hasHydrated);
