'use client';

import { Header } from '@/components/layout/header';
import { MobileNav } from '@/components/navigation/mobile-nav';
import { DesktopNav, DesktopHeader } from '@/components/navigation/desktop-nav';
import { ViewIndicator } from '@/components/navigation/swipe-view';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { ErrorTrigger } from '@/components/ui/error-trigger';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      {/* Desktop sidebar navigation */}
      <DesktopNav />

      {/* Mobile header */}
      <div className="md:hidden">
        <Header />
      </div>

      {/* Main content area */}
      <div className="md:ml-64">
        {/* Desktop header */}
        <DesktopHeader />

        {/* Content */}
        <main className="container mx-auto px-4 py-6 pb-24 md:pb-6">
          <ErrorBoundary>
            <ErrorTrigger>
              {children}
            </ErrorTrigger>
          </ErrorBoundary>
        </main>

        {/* Mobile view indicator (swipe hints) */}
        <div className="fixed bottom-20 left-0 right-0 md:hidden">
          <ViewIndicator />
        </div>
      </div>

      {/* Mobile bottom navigation */}
      <MobileNav />
    </div>
  );
}
