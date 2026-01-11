export type AuthType = 'anonymous' | 'email' | 'google' | 'github';

// Feature 1173: Federation type aliases
export type UserRole = 'anonymous' | 'free' | 'paid' | 'operator';
export type VerificationStatus = 'none' | 'pending' | 'verified';
export type ProviderType = 'email' | 'google' | 'github';

export interface User {
  userId: string;
  authType: AuthType;
  email?: string;
  createdAt: string;
  configurationCount: number;
  alertCount: number;
  emailNotificationsEnabled: boolean;
  // Feature 1173: Federation fields for RBAC-aware UI
  role?: UserRole;
  linkedProviders?: ProviderType[];
  verification?: VerificationStatus;
  lastProviderUsed?: ProviderType;
  // Feature 1191: Subscription fields for tier upgrade
  subscriptionActive?: boolean;
  subscriptionExpiresAt?: string;
  roleAssignedAt?: string;
}

export interface AuthTokens {
  idToken: string;
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

export interface AnonymousSession {
  userId: string;
  authType: 'anonymous';
  createdAt: string;
  sessionExpiresAt: string;
  storageHint: 'localStorage';
}

/**
 * Raw anonymous session response from backend (snake_case per API contract).
 * See: specs/006-user-config-dashboard/contracts/auth-api.md:31-39
 * Mapped to AnonymousSession (camelCase) at API boundary.
 */
export interface AnonymousSessionResponse {
  user_id: string;
  auth_type: 'anonymous';
  created_at: string;
  session_expires_at: string;
  storage_hint: 'localStorage';
}

export interface AuthState {
  isAuthenticated: boolean;
  isAnonymous: boolean;
  user: User | null;
  tokens: AuthTokens | null;
  sessionExpiresAt: string | null;
}

export interface MagicLinkRequest {
  email: string;
  captchaToken: string;
}

export interface MagicLinkResponse {
  message: string;
  expiresIn: number;
}

export type OAuthProvider = 'google' | 'github';

export interface SessionInfo {
  isValid: boolean;
  expiresAt: string | null;
  remainingMs: number;
}
