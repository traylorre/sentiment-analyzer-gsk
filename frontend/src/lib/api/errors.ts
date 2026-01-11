/**
 * Auth Error Handlers (Feature 1190 / A23)
 *
 * Handles AUTH_013-AUTH_018 error codes from the backend.
 * Each handler takes appropriate action based on the error type.
 */

import { useAuthStore } from '@/stores/auth-store';

/**
 * Auth error code types from backend (spec-v2.md A23).
 */
export type AuthErrorCode =
  | 'AUTH_013' // Credentials changed
  | 'AUTH_014' // Session limit exceeded
  | 'AUTH_015' // Unknown OAuth provider
  | 'AUTH_016' // OAuth provider mismatch
  | 'AUTH_017' // Password requirements not met
  | 'AUTH_018'; // Token audience invalid

/**
 * User-friendly messages for each error code.
 * These are displayed to the user and don't leak sensitive info.
 */
export const AUTH_ERROR_MESSAGES: Record<AuthErrorCode, string> = {
  AUTH_013: 'Your password was changed. Please sign in again.',
  AUTH_014: 'You have been signed out because you logged in on another device.',
  AUTH_015: 'This login provider is not supported.',
  AUTH_016: 'Login failed. Please try again.',
  AUTH_017: 'Password does not meet requirements.',
  AUTH_018: 'Session expired. Please sign in again.',
};

/**
 * Clear tokens and redirect to login page.
 */
function clearTokensAndRedirect(message?: string): void {
  const { reset, setError } = useAuthStore.getState();
  reset();
  if (message) {
    setError(message);
  }
  // Redirect to home/login page
  if (typeof window !== 'undefined') {
    window.location.href = '/';
  }
}

/**
 * Show an error message without redirecting.
 */
function showError(message: string): void {
  const { setError } = useAuthStore.getState();
  setError(message);
}

/**
 * Restart the OAuth flow (for AUTH_016 - provider mismatch).
 */
function restartOAuthFlow(): void {
  // Clear error and let user retry
  const { setError, setLoading } = useAuthStore.getState();
  setError('Login failed. Please try again.');
  setLoading(false);
  // User can click OAuth button again
}

/**
 * Show password requirements (for AUTH_017).
 * In a real implementation, this might open a modal or scroll to requirements.
 */
function showPasswordRequirements(): void {
  const { setError } = useAuthStore.getState();
  setError(
    'Password must be at least 8 characters with uppercase, lowercase, number, and special character.'
  );
}

/**
 * Handler functions for each auth error code.
 */
export const AUTH_ERROR_HANDLERS: Record<AuthErrorCode, () => void> = {
  AUTH_013: () => clearTokensAndRedirect(AUTH_ERROR_MESSAGES.AUTH_013),
  AUTH_014: () => clearTokensAndRedirect(AUTH_ERROR_MESSAGES.AUTH_014),
  AUTH_015: () => showError(AUTH_ERROR_MESSAGES.AUTH_015),
  AUTH_016: () => restartOAuthFlow(),
  AUTH_017: () => showPasswordRequirements(),
  AUTH_018: () => clearTokensAndRedirect(AUTH_ERROR_MESSAGES.AUTH_018),
};

/**
 * Check if an error code is an AUTH error.
 */
export function isAuthError(code: string): code is AuthErrorCode {
  return code.startsWith('AUTH_') && code in AUTH_ERROR_HANDLERS;
}

/**
 * Handle an auth error by calling the appropriate handler.
 *
 * @param code - The error code from the backend
 * @returns true if the error was handled, false otherwise
 */
export function handleAuthError(code: string): boolean {
  if (isAuthError(code)) {
    AUTH_ERROR_HANDLERS[code]();
    return true;
  }
  return false;
}
