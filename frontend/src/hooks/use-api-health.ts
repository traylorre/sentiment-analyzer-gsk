/**
 * Feature 1226: API Health Hook
 *
 * Wires the api-health-store to React Query's QueryCache callbacks.
 * Must be rendered inside QueryClientProvider.
 *
 * Listens to all query errors/successes and feeds them into the
 * health store for passive connectivity detection (FR-002, FR-010).
 */

import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useApiHealthStore } from '@/stores/api-health-store';

export function useApiHealth() {
  const queryClient = useQueryClient();
  const recordFailure = useApiHealthStore((s) => s.recordFailure);
  const recordSuccess = useApiHealthStore((s) => s.recordSuccess);

  useEffect(() => {
    const queryCache = queryClient.getQueryCache();

    const unsubscribe = queryCache.subscribe((event) => {
      if (!event?.query) return;

      const { state } = event.query;

      // Only react to settled queries (not fetching/cancelled)
      if (event.type === 'updated' && state.status === 'error') {
        // Don't count cancelled queries as failures
        if (state.fetchStatus === 'idle') {
          recordFailure();
        }
      }

      if (event.type === 'updated' && state.status === 'success') {
        recordSuccess();
      }
    });

    return unsubscribe;
  }, [queryClient, recordFailure, recordSuccess]);
}
