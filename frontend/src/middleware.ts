import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// M1 WI-5 (Q-M1-2 resolved 2026-07-23): cookie-based route gating removed.
//
// This middleware previously redirected /alerts and /admin based on
// `sentiment-access-token` / `sentiment-is-anonymous` cookies that nothing had
// set since Feature 1145 deleted the client cookie setter (CVSS 8.6 XSS fix) —
// so every user, including valid OAuth users, was bounced off those routes.
// The HttpOnly refresh cookie lives on the API Gateway domain and can never
// reach this middleware (Amplify domain), so any middleware-readable auth
// cookie would have to be JS-written — the exact pattern 1145 removed.
//
// Route gating now happens client-side via ProtectedRoute (requireUpgraded)
// in the /alerts and /admin layouts; actual enforcement is backend Bearer
// auth + require_role_middleware. This middleware only sets security headers.
export function middleware(_request: NextRequest) {
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
