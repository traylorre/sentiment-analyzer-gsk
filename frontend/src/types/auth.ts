export type AuthType = 'anonymous' | 'email' | 'google' | 'github';

export interface User {
  userId: string;
  authType: AuthType;
  email?: string;
  createdAt: string;
  configurationCount: number;
  alertCount: number;
  emailNotificationsEnabled: boolean;
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
