'use client';

import { DesktopNav, DesktopHeader } from '@/components/navigation/desktop-nav';
import { MobileNav } from '@/components/navigation/mobile-nav';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { ForbiddenPage } from '@/components/admin/forbidden-page';
import { useIsOperator, useIsOperatorLoading } from '@/hooks/use-operator';

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const isOperator = useIsOperator();
  const isLoading = useIsOperatorLoading();

  // Tier 2: Client-side authorization check
  // (Tier 1: middleware already verified authentication)
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
