'use client';

import { Header } from '@/components/layout/header';
import { MobileNav } from '@/components/navigation/mobile-nav';
import { DesktopNav, DesktopHeader } from '@/components/navigation/desktop-nav';
import { ViewIndicator } from '@/components/navigation/swipe-view';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { ErrorTrigger } from '@/components/ui/error-trigger';
import { useConfigStore } from '@/stores/config-store';
import { useSentiment } from '@/hooks/use-sentiment';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const activeConfigId = useConfigStore((s) => s.activeConfigId);
  const { data: sentimentData } = useSentiment(activeConfigId);
  const lastUpdated = sentimentData?.lastUpdated ?? null;
  return (
    <div className="min-h-screen bg-background">
      {/* Desktop sidebar navigation */}
      <DesktopNav />

      {/* Mobile header */}
      <div className="md:hidden">
        <Header lastUpdated={lastUpdated} />
      </div>

      {/* Main content area */}
      <div className="md:ml-64">
        {/* Desktop header */}
        <DesktopHeader lastUpdated={lastUpdated} />

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
