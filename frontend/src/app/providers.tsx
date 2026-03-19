'use client';

import { useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TooltipProvider } from '@/components/ui/tooltip';
import { STALE_TIME_MS } from '@/lib/constants';
import { useRuntimeStore } from '@/stores/runtime-store';
import { useApiHealth } from '@/hooks/use-api-health';
import { ApiHealthBanner } from '@/components/ui/api-health-banner';
import { AuthDegradationToast } from '@/components/ui/auth-degradation-toast';

interface ProvidersProps {
  children: React.ReactNode;
}

/**
 * Feature 1100: Runtime config initializer
 * Fetches runtime config on app mount to get SSE Lambda URL
 */
function RuntimeInitializer() {
  const initialize = useRuntimeStore((state) => state.initialize);

  useEffect(() => {
    // Non-blocking: fetch runtime config in background
    initialize();
  }, [initialize]);

  return null;
}

/**
 * Feature 1226: API health monitor
 * Passively tracks request outcomes for connectivity detection (FR-002).
 */
function ApiHealthMonitor() {
  useApiHealth();
  return null;
}

export function Providers({ children }: ProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: STALE_TIME_MS,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <RuntimeInitializer />
      <ApiHealthMonitor />
      <ApiHealthBanner />
      <AuthDegradationToast />
      <TooltipProvider delayDuration={300}>
        {children}
      </TooltipProvider>
    </QueryClientProvider>
  );
}
