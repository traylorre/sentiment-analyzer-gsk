/**
 * Components Contract
 * Feature: 1122-zustand-hydration-fix
 *
 * Defines the interface for auth-related components after hydration fix.
 */

import type { ReactNode } from 'react'

// ============================================================================
// ProtectedRoute Component Contract
// ============================================================================

export interface ProtectedRouteProps {
  /**
   * Content to render when access is granted.
   */
  children: ReactNode

  /**
   * Whether authentication is required (any auth type).
   * @default true
   */
  requireAuth?: boolean

  /**
   * Whether upgraded (non-anonymous) authentication is required.
   * @default false
   */
  requireUpgraded?: boolean

  /**
   * Optional fallback UI to show instead of redirecting.
   * If not provided, redirects to `redirectTo`.
   */
  fallback?: ReactNode

  /**
   * URL to redirect to when access is denied.
   * @default '/auth/signin'
   */
  redirectTo?: string
}

/**
 * Rendering logic (in order):
 *
 * 1. If !hasHydrated → render loading spinner
 * 2. If !isInitialized || isLoading → render loading spinner
 * 3. If requireAuth && !isAuthenticated:
 *    - If fallback → render fallback
 *    - Else → redirect to redirectTo
 * 4. If requireUpgraded && isAnonymous:
 *    - Render upgrade prompt
 * 5. Else → render children
 */

// ============================================================================
// UserMenu Component Contract
// ============================================================================

/**
 * UserMenu has no external props - all state is derived from hooks.
 *
 * Rendering logic:
 *
 * 1. If !hasHydrated → render UserMenuSkeleton
 * 2. If !isAuthenticated → render SignInButton
 * 3. If isAuthenticated → render UserDropdown with:
 *    - Display name (Guest for anonymous, email username for authenticated)
 *    - Auth type badge
 *    - Menu items based on auth type
 */

export interface UserMenuSkeletonProps {
  /**
   * Width of the skeleton.
   * @default '120px'
   */
  width?: string
}

// ============================================================================
// AuthGuard Component Contract
// ============================================================================

export interface AuthGuardProps {
  /**
   * Content to render when access is granted.
   */
  children: ReactNode

  /**
   * Feature requiring auth.
   * Only 'alerts' requires upgraded auth.
   */
  feature?: 'alerts' | 'configs' | 'settings'

  /**
   * Fallback UI when access is denied.
   */
  fallback?: ReactNode
}

/**
 * AuthGuard is a lighter-weight alternative to ProtectedRoute.
 * Used for feature-level access control within already-authenticated pages.
 *
 * Rendering logic:
 *
 * 1. If !hasHydrated → render nothing (parent should handle loading)
 * 2. If feature === 'alerts' && isAnonymous → render fallback or nothing
 * 3. Else → render children
 */

// ============================================================================
// Skeleton Components Contract
// ============================================================================

/**
 * Skeleton component for UserMenu during hydration.
 * Shows a neutral placeholder that doesn't flash as sign-in button.
 */
export interface UserMenuSkeletonSpec {
  /**
   * Visual appearance:
   * - Rounded rectangle matching button dimensions
   * - Animated shimmer effect
   * - Same position as final UserMenu
   */
  dimensions: {
    width: string  // e.g., '120px'
    height: string // e.g., '40px'
  }
}

/**
 * Skeleton component for ProtectedRoute content during hydration.
 * Shows a loading spinner centered in the content area.
 */
export interface ProtectedRouteLoadingSpec {
  /**
   * Visual appearance:
   * - Centered spinner animation
   * - Full height of parent container
   * - Accessible loading indicator (aria-busy)
   */
  accessibility: {
    role: 'status'
    ariaLabel: 'Loading'
  }
}
