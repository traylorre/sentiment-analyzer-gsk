// Cookie utilities for auth state synchronization with middleware

const COOKIE_OPTIONS = {
  path: '/',
  sameSite: 'lax' as const,
  secure: process.env.NODE_ENV === 'production',
};

export function setAuthCookies(accessToken: string, isAnonymous: boolean): void {
  if (typeof document === 'undefined') return;

  // Set access token cookie (for middleware to check)
  document.cookie = `sentiment-access-token=${accessToken}; path=${COOKIE_OPTIONS.path}; samesite=${COOKIE_OPTIONS.sameSite}${COOKIE_OPTIONS.secure ? '; secure' : ''}`;

  // Set anonymous flag cookie
  document.cookie = `sentiment-is-anonymous=${isAnonymous}; path=${COOKIE_OPTIONS.path}; samesite=${COOKIE_OPTIONS.sameSite}${COOKIE_OPTIONS.secure ? '; secure' : ''}`;
}

export function clearAuthCookies(): void {
  if (typeof document === 'undefined') return;

  // Clear cookies by setting them to expire in the past
  document.cookie = `sentiment-access-token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
  document.cookie = `sentiment-is-anonymous=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
}

export function getAuthCookie(): string | null {
  if (typeof document === 'undefined') return null;

  const match = document.cookie.match(/sentiment-access-token=([^;]+)/);
  return match ? match[1] : null;
}

export function getIsAnonymousCookie(): boolean {
  if (typeof document === 'undefined') return false;

  const match = document.cookie.match(/sentiment-is-anonymous=([^;]+)/);
  return match ? match[1] === 'true' : false;
}
