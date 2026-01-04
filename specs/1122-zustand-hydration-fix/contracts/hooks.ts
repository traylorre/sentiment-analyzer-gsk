/**
 * Hooks Contract
 * Feature: 1122-zustand-hydration-fix
 *
 * Defines the interface for auth-related hooks after hydration fix.
 */

import type { User, AuthTokens } from './auth-store'

// ============================================================================
// useAuth Hook Contract
// ============================================================================

export interface UseAuthReturn {
  // === User State ===
  user: User | null
  tokens: AuthTokens | null

  // === Status Flags ===
  isAuthenticated: boolean
  isAnonymous: boolean
  isLoading: boolean
  isInitialized: boolean

  // === NEW: Hydration Status ===
  /**
   * Whether zustand persist has completed rehydrating.
   * Components should check this before relying on auth state.
   */
  hasHydrated: boolean

  // === Session Info ===
  remainingSessionMs: number | null
  isSessionValid: boolean

  // === Actions ===
  requestMagicLink: (email: string) => Promise<void>
  verifyToken: (token: string) => Promise<void>
  signInOAuth: (provider: 'google' | 'github') => Promise<{ url: string }>
  handleCallback: (code: string, provider: string) => Promise<void>
  handleSignOut: () => Promise<void>
  refreshSession: () => Promise<void>
}

// ============================================================================
// useSessionInit Hook Contract
// ============================================================================

export interface UseSessionInitReturn {
  /**
   * True while session initialization is in progress.
   * Note: Stays false until hydration completes (does not start init before hydration).
   */
  isInitializing: boolean

  /**
   * True if initialization encountered an error.
   */
  isError: boolean

  /**
   * Error object if initialization failed, null otherwise.
   */
  error: Error | null

  /**
   * True when initialization is complete and successful.
   * This means:
   * 1. Hydration is complete
   * 2. Session is established (either restored or newly created)
   */
  isReady: boolean
}

/**
 * State transitions for useSessionInit:
 *
 * 1. Initial (pre-hydration):
 *    { isInitializing: false, isError: false, error: null, isReady: false }
 *
 * 2. Hydrated, starting init:
 *    { isInitializing: true, isError: false, error: null, isReady: false }
 *
 * 3a. Success:
 *    { isInitializing: false, isError: false, error: null, isReady: true }
 *
 * 3b. Failure:
 *    { isInitializing: false, isError: true, error: Error, isReady: false }
 */

// ============================================================================
// useChartData Hook Contract (Hydration-Aware)
// ============================================================================

export interface UseChartDataOptions {
  /**
   * Configuration ID to fetch chart data for.
   */
  configId: string

  /**
   * Time range for chart data.
   */
  timeRange?: '1D' | '1W' | '1M' | '3M' | '1Y' | 'ALL'
}

export interface UseChartDataReturn {
  data: ChartDataPoint[] | undefined
  isLoading: boolean
  isError: boolean
  error: Error | null
  refetch: () => Promise<void>
}

export interface ChartDataPoint {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  sentiment?: number
}

/**
 * Implementation requirements:
 *
 * 1. MUST wait for hydration before enabling query
 * 2. MUST include userId in queryKey for cache isolation
 * 3. MUST re-enable query when userId transitions null → valid
 *
 * @example
 * const { enabled } = useQuery({
 *   queryKey: ['chart-data', userId, configId],
 *   enabled: hasHydrated && !!userId && !!configId,
 * })
 */

// ============================================================================
// useHasHydrated Hook Contract
// ============================================================================

/**
 * Simple hook to check hydration status.
 * Subscribes to _hasHydrated state in auth store.
 *
 * @returns boolean - true if zustand persist has completed rehydration
 *
 * @example
 * function MyComponent() {
 *   const hasHydrated = useHasHydrated()
 *   if (!hasHydrated) return <Skeleton />
 *   return <Content />
 * }
 */
export type UseHasHydrated = () => boolean
