'use client';

import { useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TooltipProvider } from '@/components/ui/tooltip';
import { STALE_TIME_MS } from '@/lib/constants';
import { useRuntimeStore } from '@/stores/runtime-store';

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
      <TooltipProvider delayDuration={300}>
        {children}
      </TooltipProvider>
    </QueryClientProvider>
  );
}
