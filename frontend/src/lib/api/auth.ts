import { api, setCsrfToken, getCsrfToken } from './client';
import { SESSION_INIT_TIMEOUT_MS } from '@/lib/constants';
import type { User, AuthTokens, AnonymousSession, AnonymousSessionResponse } from '@/types/auth';

/**
 * Map snake_case backend response to camelCase frontend type.
 * Per API contract: specs/006-user-config-dashboard/contracts/auth-api.md:31-39
 */
function mapAnonymousSession(response: AnonymousSessionResponse): AnonymousSession {
  return {
    userId: response.user_id,
    token: response.token,
    authType: response.auth_type,
    createdAt: response.created_at,
    sessionExpiresAt: response.session_expires_at,
    storageHint: response.storage_hint,
  };
}

/**
 * Raw /api/v2/auth/me response (snake_case per API contract).
 * Feature 1174: Includes federation fields from Feature 1172.
 */
interface UserMeResponse {
  auth_type: string;
  email_masked: string | null;
  configs_count: number;
  max_configs: number;
  session_expires_in_seconds: number | null;
  role: string;
  linked_providers: string[];
  verification: string;
  last_provider_used: string | null;
}

/**
 * Raw /api/v2/auth/oauth/callback response (snake_case per API contract).
 * Feature 1177: Maps backend OAuthCallbackResponse to frontend types.
 */
interface OAuthCallbackResponse {
  status: string;
  email_masked: string | null;
  auth_type: string | null;
  tokens: {
    id_token: string;
    access_token: string;
    expires_in: number;
  } | null;
  // Feature 1396 (N2): body-delivered CSRF token (echoed as X-CSRF-Token on /refresh).
  csrf_token?: string | null;
  merged_anonymous_data: boolean;
  is_new_user: boolean;
  conflict: boolean;
  existing_provider: string | null;
  message: string | null;
  error: string | null;
  // Feature 1176: Federation fields
  role: string;
  verification: string;
  linked_providers: string[];
  last_provider_used: string | null;
}

/**
 * Raw /api/v2/auth/oauth/urls response (snake_case per API contract).
 * Feature 1193: Includes provider-specific state for CSRF protection.
 */
interface OAuthProviderInfo {
  authorize_url: string;
  icon: string;
  state: string; // Provider-specific CSRF state
}

export interface OAuthUrlsResponse {
  providers: {
    google: OAuthProviderInfo;
    github: OAuthProviderInfo;
  };
  state: string; // Legacy compatibility
}

/**
 * Map /api/v2/auth/me snake_case response to camelCase User type.
 * Feature 1174: Maps federation fields for RBAC-aware UI.
 */
function mapUserMeResponse(response: UserMeResponse): Partial<User> {
  return {
    authType: response.auth_type as User['authType'],
    email: response.email_masked ?? undefined,
    configurationCount: response.configs_count,
    // Feature 1174: Federation fields
    role: response.role as User['role'],
    linkedProviders: response.linked_providers as User['linkedProviders'],
    verification: response.verification as User['verification'],
    lastProviderUsed: (response.last_provider_used ?? undefined) as User['lastProviderUsed'],
  };
}

/**
 * Map /api/v2/auth/oauth/callback snake_case response to camelCase AuthResponse.
 * Feature 1177: Extracts federation fields for frontend RBAC-aware UI.
 *
 * Note: OAuth response doesn't include all User fields (userId, createdAt, etc.)
 * These are set to placeholder values; auth store should merge with existing user data.
 */
function mapOAuthCallbackResponse(response: OAuthCallbackResponse): AuthResponse {
  // Handle error/conflict responses
  if (response.status === 'error' || response.error) {
    throw new Error(response.error ?? response.message ?? 'OAuth authentication failed');
  }
  if (response.status === 'conflict') {
    throw new Error(
      response.message ?? `Account conflict: email already registered via ${response.existing_provider}`
    );
  }

  return {
    user: {
      // Placeholder fields - OAuth callback doesn't return these
      userId: '', // Will be populated from session or /me endpoint
      createdAt: new Date().toISOString(),
      configurationCount: 0,
      alertCount: 0,
      emailNotificationsEnabled: false,
      // Fields from OAuth response
      authType: (response.auth_type ?? 'anonymous') as User['authType'],
      email: response.email_masked ?? undefined,
      // Feature 1177: Federation fields from Feature 1176
      role: (response.role ?? 'anonymous') as User['role'],
      linkedProviders: (response.linked_providers ?? []) as User['linkedProviders'],
      verification: (response.verification ?? 'none') as User['verification'],
      lastProviderUsed: (response.last_provider_used ?? undefined) as User['lastProviderUsed'],
    },
    tokens: response.tokens
      ? {
          idToken: response.tokens.id_token,
          accessToken: response.tokens.access_token,
          refreshToken: '', // Refresh token is httpOnly cookie, not in response body
          expiresIn: response.tokens.expires_in,
        }
      : {
          idToken: '',
          accessToken: '',
          refreshToken: '',
          expiresIn: 0,
        },
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
  accessToken: string | null;
  idToken: string | null;
  expiresIn: number;
  // M1 WI-3: guest-session restore fields (null for Cognito-backed refreshes)
  userId: string | null;
  authType: string | null;
  sessionExpiresAt: string | null;
}

/** Raw backend shape for POST /api/v2/auth/refresh (snake_case). */
interface RefreshTokenResponseRaw {
  access_token?: string | null;
  id_token?: string | null;
  expires_in?: number;
  user_id?: string | null;
  auth_type?: string | null;
  session_expires_at?: string | null;
  // Feature 1396 (N2): rotated body-delivered CSRF token for the next /refresh echo.
  csrf_token?: string | null;
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
   * Get OAuth authorization URLs for all providers.
   * Feature 1193: Returns provider-specific state for CSRF protection.
   */
  getOAuthUrls: () => api.get<OAuthUrlsResponse>('/api/v2/auth/oauth/urls'),

  /**
   * Exchange OAuth code for tokens.
   * Feature 1177: Maps backend OAuthCallbackResponse to frontend AuthResponse with federation fields.
   * Feature 1193: Requires state and redirect_uri for CSRF validation.
   */
  exchangeOAuthCode: async (
    provider: 'google' | 'github',
    code: string,
    state: string,
    redirectUri: string
  ): Promise<AuthResponse> => {
    const response = await api.post<OAuthCallbackResponse>('/api/v2/auth/oauth/callback', {
      provider,
      code,
      state,
      redirect_uri: redirectUri,
    });
    // Feature 1396 (N2): remember the body-delivered CSRF token so the next /refresh
    // can echo it as X-CSRF-Token (the API-domain cookie is unreadable cross-origin).
    if (response.csrf_token) {
      setCsrfToken(response.csrf_token);
    }
    return mapOAuthCallbackResponse(response);
  },

  /**
   * Refresh access token using httpOnly cookie
   * Feature 1168: Refresh token sent via cookie only, not in request body
   * M1 WI-3: maps the snake_case backend response explicitly (the previous
   * unmapped version silently yielded accessToken === undefined) and carries
   * the guest-restore fields (user_id/auth_type/session_expires_at).
   */
  refreshToken: async (): Promise<RefreshTokenResponse> => {
    // Feature 1396 (N2): echo the in-memory CSRF token as X-CSRF-Token. The backend
    // double-submit compares it against the browser-auto-attached API-domain cookie.
    // (During the migration window /refresh stays CSRF-exempt; sending the header early
    // is harmless and lets the exemption be dropped later without a frontend redeploy.)
    const csrf = getCsrfToken();
    const raw = await api.post<RefreshTokenResponseRaw>(
      '/api/v2/auth/refresh',
      undefined,
      csrf ? { headers: { 'X-CSRF-Token': csrf } } : undefined
    );
    // Rotate the stored CSRF token to the freshly-issued value for the next refresh.
    if (raw.csrf_token) {
      setCsrfToken(raw.csrf_token);
    }
    return {
      accessToken: raw.access_token ?? null,
      idToken: raw.id_token ?? null,
      expiresIn: raw.expires_in ?? 0,
      userId: raw.user_id ?? null,
      authType: raw.auth_type ?? null,
      sessionExpiresAt: raw.session_expires_at ?? null,
    };
  },

  /**
   * Extend the current session
   */
  extendSession: () =>
    api.post<{ expiresAt: string }>('/api/v2/auth/extend'),

  /**
   * Get current user profile with federation fields.
   * Feature 1174: Maps snake_case response to camelCase User type.
   */
  getProfile: async (): Promise<Partial<User>> => {
    const response = await api.get<UserMeResponse>('/api/v2/auth/me');
    return mapUserMeResponse(response);
  },

  /**
   * Sign out and invalidate tokens
   */
  signOut: () =>
    api.post<void>('/api/v2/auth/signout'),
};
