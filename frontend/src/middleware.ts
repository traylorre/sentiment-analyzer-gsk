import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Routes that require authentication
// NOTE: /settings was removed from protected routes because:
// 1. Anonymous users have valid settings to customize (haptic, motion, notifications)
// 2. The auth cookie mechanism is client-side only, but middleware runs server-side
// 3. This caused a redirect loop: middleware blocks → React never loads → cookies never set
// Protected routes should only include features truly unavailable to anonymous users
const protectedRoutes: string[] = [];

// Routes that require upgraded (non-anonymous) auth
const upgradedRoutes = ['/alerts'];

// Routes that should redirect to dashboard if already authenticated
const authRoutes = ['/auth/signin'];

// Public routes that don't need any auth check
const publicRoutes = ['/', '/auth/verify', '/terms', '/privacy'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Get auth tokens from cookies (set by client-side auth)
  const accessToken = request.cookies.get('sentiment-access-token')?.value;
  const isAnonymous = request.cookies.get('sentiment-is-anonymous')?.value === 'true';

  const isAuthenticated = !!accessToken;
  const hasUpgradedAuth = isAuthenticated && !isAnonymous;

  // Check if current path matches any route patterns
  const isProtectedRoute = protectedRoutes.some((route) =>
    pathname.startsWith(route)
  );
  const isUpgradedRoute = upgradedRoutes.some((route) =>
    pathname.startsWith(route)
  );
  const isAuthRoute = authRoutes.some((route) => pathname.startsWith(route));

  // Redirect to sign in if accessing protected route without auth
  if (isProtectedRoute && !isAuthenticated) {
    const signInUrl = new URL('/auth/signin', request.url);
    signInUrl.searchParams.set('redirect', pathname);
    return NextResponse.redirect(signInUrl);
  }

  // Redirect to sign in if accessing upgraded route without proper auth
  if (isUpgradedRoute && !hasUpgradedAuth) {
    const signInUrl = new URL('/auth/signin', request.url);
    signInUrl.searchParams.set('redirect', pathname);
    signInUrl.searchParams.set('upgrade', 'true');
    return NextResponse.redirect(signInUrl);
  }

  // Redirect to dashboard if already authenticated and accessing auth routes
  if (isAuthRoute && hasUpgradedAuth) {
    return NextResponse.redirect(new URL('/', request.url));
  }

  // Add security headers to all responses
  const response = NextResponse.next();

  // Security headers
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('X-XSS-Protection', '1; mode=block');
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');

  // Permissions policy
  response.headers.set(
    'Permissions-Policy',
    'camera=(), microphone=(), geolocation=(), interest-cohort=()'
  );

  return response;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder files
     * - API routes (handled separately)
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
