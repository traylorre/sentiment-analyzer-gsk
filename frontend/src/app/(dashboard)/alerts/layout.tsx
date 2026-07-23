'use client';

// Target: Customer Dashboard (Next.js/Amplify)
//
// M1 WI-5 (Q-M1-2): /alerts requires an upgraded (non-anonymous) session.
// Gating is client-side — the middleware cannot see auth state (the HttpOnly
// refresh cookie belongs to the API Gateway domain). Real enforcement is the
// backend rejecting non-upgraded Bearer tokens; this guard is the UX layer
// that redirects guests to /auth/signin?redirect=%2Falerts&upgrade=true.

import { ProtectedRoute } from '@/components/auth/protected-route';

export default function AlertsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ProtectedRoute requireUpgraded>{children}</ProtectedRoute>;
}
