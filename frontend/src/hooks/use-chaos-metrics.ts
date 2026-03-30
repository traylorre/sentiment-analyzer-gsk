import { useQuery } from '@tanstack/react-query';
import { chaosApi } from '@/lib/api/chaos';
import { ApiClientError } from '@/lib/api/client';

export function useMetrics() {
  const query = useQuery({
    queryKey: ['chaos', 'metrics'],
    queryFn: () => chaosApi.getMetrics(),
    refetchInterval: 30_000,
    retry: (failureCount, error) => {
      // Don't retry 403 (metrics unavailable in environment)
      if (error instanceof ApiClientError && error.status === 403) return false;
      // Don't retry 429 (rate limited) — will retry on next interval
      if (error instanceof ApiClientError && error.status === 429) return false;
      return failureCount < 2;
    },
  });

  const isUnavailable =
    query.error instanceof ApiClientError && query.error.status === 403;
  const isRateLimited =
    query.error instanceof ApiClientError && query.error.status === 429;

  return {
    ...query,
    isUnavailable,
    isRateLimited,
  };
}
