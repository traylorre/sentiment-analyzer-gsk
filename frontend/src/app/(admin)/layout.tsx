'use client';

import { DesktopNav, DesktopHeader } from '@/components/navigation/desktop-nav';
import { MobileNav } from '@/components/navigation/mobile-nav';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { ForbiddenPage } from '@/components/admin/forbidden-page';
import { ProtectedRoute } from '@/components/auth/protected-route';
import { useIsOperator, useIsOperatorLoading } from '@/hooks/use-operator';

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute requireUpgraded>
      <AdminLayoutInner>{children}</AdminLayoutInner>
    </ProtectedRoute>
  );
}

function AdminLayoutInner({
  children,
}: {
  children: React.ReactNode;
}) {
  const isOperator = useIsOperator();
  const isLoading = useIsOperatorLoading();

  // Tier 2: Client-side authorization check (operator role via /me).
  // Tier 1 (upgraded auth) is the ProtectedRoute wrapper above — M1 WI-5
  // moved it here from the middleware, whose cookie gate had been dead since
  // Feature 1145 (Q-M1-2). Backend require_role_middleware("operator") remains
  // the actual security boundary.
  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <DesktopNav />
        <div className="md:ml-64">
          <DesktopHeader title="Loading..." />
          <main className="container mx-auto px-4 py-6">
            <div className="animate-pulse space-y-4">
              <div className="h-8 bg-muted rounded w-48" />
              <div className="h-64 bg-muted rounded" />
            </div>
          </main>
        </div>
        <MobileNav />
      </div>
    );
  }

  if (!isOperator) {
    return (
      <div className="min-h-screen bg-background">
        <DesktopNav />
        <div className="md:ml-64">
          <DesktopHeader title="Access Denied" />
          <main className="container mx-auto px-4 py-6 pb-24 md:pb-6">
            <ForbiddenPage />
          </main>
        </div>
        <MobileNav />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <DesktopNav />
      <div className="md:hidden">
        {/* Mobile uses same header pattern as dashboard */}
      </div>
      <div className="md:ml-64">
        <DesktopHeader title="Admin" />
        <main className="container mx-auto px-4 py-6 pb-24 md:pb-6">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </div>
      <MobileNav />
    </div>
  );
}
