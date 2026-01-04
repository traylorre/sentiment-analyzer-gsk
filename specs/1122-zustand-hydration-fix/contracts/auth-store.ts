/**
 * Auth Store Contract
 * Feature: 1122-zustand-hydration-fix
 *
 * This contract defines the interface for the auth store after hydration fix.
 */

// ============================================================================
// State Interface
// ============================================================================

export interface User {
  userId: string
  authType: 'anonymous' | 'email' | 'google' | 'github'
  email?: string
  createdAt: string
  configurationCount: number
  alertCount: number
  emailNotificationsEnabled: boolean
}

export interface AuthTokens {
  idToken: string
  accessToken: string
  refreshToken: string
  expiresIn: number
}

export interface AuthState {
  // === Identity ===
  user: User | null
  tokens: AuthTokens | null
  sessionExpiresAt: string | null

  // === Status Flags ===
  isAuthenticated: boolean
  isAnonymous: boolean
  isLoading: boolean
  error: string | null
  isInitialized: boolean

  // === NEW: Hydration Tracking ===
  /**
   * Indicates whether zustand persist has completed rehydrating from localStorage.
   * - Starts as `false` on store creation (SSR-safe)
   * - Set to `true` via onRehydrateStorage callback
   * - NOT persisted to localStorage
   *
   * Components MUST check this before reading auth state to avoid race conditions.
   */
  _hasHydrated: boolean
}

// ============================================================================
// Actions Interface
// ============================================================================

export interface AuthActions {
  // === Authentication ===
  signInAnonymous: () => Promise<void>
  signInOAuth: (provider: 'google' | 'github') => Promise<{ url: string }>
  requestMagicLink: (email: string) => Promise<void>
  verifyMagicLink: (token: string) => Promise<void>
  handleOAuthCallback: (code: string, provider: string) => Promise<void>
  signOut: () => Promise<void>

  // === Session Management ===
  refreshSession: () => Promise<void>
  extendSession: () => Promise<void>
  isSessionValid: () => boolean

  // === State Management ===
  setUser: (user: User | null) => void
  setTokens: (tokens: AuthTokens | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setInitialized: (initialized: boolean) => void
  clearAuth: () => void
}

// ============================================================================
// Store Type
// ============================================================================

export type AuthStore = AuthState & AuthActions

// ============================================================================
// Selector Hooks Contract
// ============================================================================

/**
 * Hook to check if zustand persist has completed hydration.
 *
 * @returns boolean - true if rehydration is complete
 *
 * @example
 * const hasHydrated = useHasHydrated()
 * if (!hasHydrated) return <Skeleton />
 */
export type UseHasHydrated = () => boolean

/**
 * Hook to get current user.
 * MUST only be called after hydration check.
 */
export type UseUser = () => User | null

/**
 * Hook to check authentication status.
 * MUST only be called after hydration check.
 */
export type UseIsAuthenticated = () => boolean

/**
 * Hook to check if user is anonymous.
 * MUST only be called after hydration check.
 */
export type UseIsAnonymous = () => boolean

/**
 * Hook to check loading state.
 */
export type UseAuthLoading = () => boolean

/**
 * Hook to get auth error.
 */
export type UseAuthError = () => string | null

// ============================================================================
// Persist Configuration Contract
// ============================================================================

export interface PersistConfig {
  name: 'sentiment-auth-tokens'
  storage: Storage // localStorage wrapper
  partialize: (state: AuthState) => Partial<AuthState>
  onRehydrateStorage: () => (state: AuthState | undefined) => void
}

/**
 * Fields that MUST be persisted to localStorage.
 */
export const PERSISTED_FIELDS = [
  'user',
  'tokens',
  'sessionExpiresAt',
  'isAuthenticated',
  'isAnonymous',
] as const

/**
 * Fields that MUST NOT be persisted (runtime-only).
 */
export const NON_PERSISTED_FIELDS = [
  '_hasHydrated',
  'isLoading',
  'error',
  'isInitialized',
] as const
