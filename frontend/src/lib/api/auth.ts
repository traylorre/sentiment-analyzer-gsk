import { api } from './client';
import { SESSION_INIT_TIMEOUT_MS } from '@/lib/constants';
import type { User, AuthTokens, AnonymousSession, AnonymousSessionResponse } from '@/types/auth';

/**
 * Map snake_case backend response to camelCase frontend type.
 * Per API contract: specs/006-user-config-dashboard/contracts/auth-api.md:31-39
 */
function mapAnonymousSession(response: AnonymousSessionResponse): AnonymousSession {
  return {
    userId: response.user_id,
    authType: response.auth_type,
    createdAt: response.created_at,
    sessionExpiresAt: response.session_expires_at,
    storageHint: response.storage_hint,
  };
}

export interface MagicLinkRequest {
  email: string;
}

export interface MagicLinkResponse {
  message: string;
  expiresIn: number;
}

export interface VerifyMagicLinkRequest {
  token: string;
  sig: string;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

// RefreshTokenRequest removed - refresh token now sent via httpOnly cookie only (Feature 1168)

export interface RefreshTokenResponse {
  accessToken: string;
  idToken: string;
  expiresIn: number;
}

export const authApi = {
  /**
   * Create a new anonymous session.
   * Maps snake_case backend response to camelCase frontend type.
   * Feature 1112: Includes timeout to prevent infinite loading state.
   * @param timeout - Optional timeout in milliseconds (default: SESSION_INIT_TIMEOUT_MS)
   */
  createAnonymousSession: async (timeout: number = SESSION_INIT_TIMEOUT_MS): Promise<AnonymousSession> => {
    const response = await api.post<AnonymousSessionResponse>('/api/v2/auth/anonymous', undefined, { timeout });
    return mapAnonymousSession(response);
  },

  /**
   * Request a magic link be sent to the provided email
   */
  requestMagicLink: (email: string) =>
    api.post<MagicLinkResponse>('/api/v2/auth/magic-link', { email }),

  /**
   * Verify a magic link token and get authenticated session
   */
  verifyMagicLink: (token: string, sig: string) =>
    api.post<AuthResponse>('/api/v2/auth/magic-link/verify', { token, sig }),

  /**
   * Get OAuth authorization URLs for all providers
   */
  getOAuthUrls: () =>
    api.get<{ google: string; github: string }>('/api/v2/auth/oauth/urls'),

  /**
   * Exchange OAuth code for tokens
   */
  exchangeOAuthCode: (provider: 'google' | 'github', code: string) =>
    api.post<AuthResponse>('/api/v2/auth/oauth/callback', { provider, code }),

  /**
   * Refresh access token using httpOnly cookie
   * Feature 1168: Refresh token sent via cookie only, not in request body
   */
  refreshToken: () =>
    api.post<RefreshTokenResponse>('/api/v2/auth/refresh'),

  /**
   * Extend the current session
   */
  extendSession: () =>
    api.post<{ expiresAt: string }>('/api/v2/auth/extend'),

  /**
   * Get current user profile
   */
  getProfile: () =>
    api.get<User>('/api/v2/auth/me'),

  /**
   * Sign out and invalidate tokens
   */
  signOut: () =>
    api.post<void>('/api/v2/auth/signout'),
};
