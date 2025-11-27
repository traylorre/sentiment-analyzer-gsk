'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { User, AuthTokens, AuthState, OAuthProvider } from '@/types/auth';
import { setAuthCookies, clearAuthCookies } from '@/lib/cookies';

interface AuthStore extends AuthState {
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
  verifyMagicLink: (token: string) => Promise<void>;
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

const initialState: AuthState & { isLoading: boolean; isInitialized: boolean; error: string | null } = {
  isAuthenticated: false,
  isAnonymous: false,
  user: null,
  tokens: null,
  sessionExpiresAt: null,
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
      },

      setTokens: (tokens) => {
        set({ tokens });
        // Sync cookies for middleware
        if (tokens?.accessToken) {
          const { isAnonymous } = get();
          setAuthCookies(tokens.accessToken, isAnonymous);
        }
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

          const response = await fetch('/api/v2/auth/anonymous', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
          });

          if (!response.ok) {
            throw new Error('Failed to create anonymous session');
          }

          const data = await response.json();

          setUser({
            userId: data.userId,
            authType: 'anonymous',
            createdAt: new Date().toISOString(),
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

      signInWithMagicLink: async (email: string, captchaToken: string) => {
        const { setLoading, setError } = get();

        try {
          setLoading(true);
          setError(null);

          const response = await fetch('/api/v2/auth/magic-link', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, captchaToken }),
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Failed to send magic link');
          }

          // Magic link sent successfully - user needs to check email
        } catch (error) {
          setError(error instanceof Error ? error.message : 'Unknown error');
          throw error;
        } finally {
          setLoading(false);
        }
      },

      verifyMagicLink: async (token: string) => {
        const { setLoading, setError, setUser, setTokens, setSession } = get();

        try {
          setLoading(true);
          setError(null);

          const response = await fetch('/api/v2/auth/magic-link/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token }),
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Invalid or expired magic link');
          }

          const data = await response.json();

          setUser(data.user);
          setTokens(data.tokens);
          setSession(data.sessionExpiresAt);
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

          // Get OAuth URL from backend
          const response = await fetch(`/api/v2/auth/oauth/${provider}/url`);

          if (!response.ok) {
            throw new Error(`Failed to get ${provider} OAuth URL`);
          }

          const { url } = await response.json();

          // Redirect to OAuth provider
          window.location.href = url;
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

          const response = await fetch(`/api/v2/auth/oauth/${provider}/callback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code }),
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'OAuth authentication failed');
          }

          const data = await response.json();

          setUser(data.user);
          setTokens(data.tokens);
          setSession(data.sessionExpiresAt);
        } catch (error) {
          setError(error instanceof Error ? error.message : 'Unknown error');
          throw error;
        } finally {
          setLoading(false);
        }
      },

      refreshSession: async () => {
        const { tokens, setTokens, setSession, setError } = get();

        if (!tokens?.refreshToken) {
          return;
        }

        try {
          const response = await fetch('/api/v2/auth/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refreshToken: tokens.refreshToken }),
          });

          if (!response.ok) {
            throw new Error('Failed to refresh session');
          }

          const data = await response.json();

          setTokens(data.tokens);
          setSession(data.sessionExpiresAt);
        } catch (error) {
          setError(error instanceof Error ? error.message : 'Unknown error');
          // Don't throw - let the session expire gracefully
        }
      },

      signOut: async () => {
        const { tokens, reset } = get();

        try {
          if (tokens?.accessToken) {
            await fetch('/api/v2/auth/logout', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${tokens.accessToken}`,
              },
            });
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
        clearAuthCookies();
        set(initialState);
      },
    }),
    {
      name: TOKEN_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        tokens: state.tokens,
        sessionExpiresAt: state.sessionExpiresAt,
        isAuthenticated: state.isAuthenticated,
        isAnonymous: state.isAnonymous,
      }),
    }
  )
);

// Selector hooks for common use cases
export const useUser = () => useAuthStore((state) => state.user);
export const useIsAuthenticated = () => useAuthStore((state) => state.isAuthenticated);
export const useIsAnonymous = () => useAuthStore((state) => state.isAnonymous);
export const useAuthLoading = () => useAuthStore((state) => state.isLoading);
export const useAuthError = () => useAuthStore((state) => state.error);
