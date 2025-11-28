import { api } from './client';
import type { User, AuthTokens, AnonymousSession } from '@/types/auth';

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

export interface RefreshTokenRequest {
  refreshToken: string;
}

export interface RefreshTokenResponse {
  accessToken: string;
  idToken: string;
  expiresIn: number;
}

export const authApi = {
  /**
   * Create a new anonymous session
   */
  createAnonymousSession: () =>
    api.post<AnonymousSession>('/api/v2/auth/anonymous'),

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
   * Refresh access token using refresh token
   */
  refreshToken: (refreshToken: string) =>
    api.post<RefreshTokenResponse>('/api/v2/auth/refresh', { refreshToken }),

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
