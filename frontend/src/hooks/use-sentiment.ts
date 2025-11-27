'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { sentimentApi } from '@/lib/api/sentiment';
import type { SentimentData, SentimentTimeSeries, SentimentSource } from '@/types/sentiment';
import { STALE_TIME_MS } from '@/lib/constants';

/**
 * Hook to fetch current sentiment data for a configuration
 */
export function useSentiment(configId: string | null) {
  return useQuery<SentimentData>({
    queryKey: ['sentiment', configId],
    queryFn: () => sentimentApi.get(configId!),
    enabled: !!configId,
    staleTime: STALE_TIME_MS,
    refetchInterval: STALE_TIME_MS, // Auto-refresh every 5 minutes
  });
}

/**
 * Hook to fetch sentiment history for a specific ticker
 */
export function useSentimentHistory(
  configId: string | null,
  ticker: string | null,
  options?: {
    source?: SentimentSource;
    days?: number;
  }
) {
  return useQuery<SentimentTimeSeries[]>({
    queryKey: ['sentiment-history', configId, ticker, options],
    queryFn: () => sentimentApi.getHistory(configId!, ticker!, options),
    enabled: !!configId && !!ticker,
    staleTime: STALE_TIME_MS,
  });
}

/**
 * Hook to manually refresh sentiment data
 */
export function useSentimentRefresh(configId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => sentimentApi.refresh(configId!),
    onSuccess: (data) => {
      // Update the cache with fresh data
      queryClient.setQueryData(['sentiment', configId], data);
    },
  });
}

/**
 * Combined hook for common sentiment operations
 */
export function useSentimentData(configId: string | null, ticker: string | null) {
  const sentiment = useSentiment(configId);
  const history = useSentimentHistory(configId, ticker);
  const refresh = useSentimentRefresh(configId);

  return {
    // Current data
    data: sentiment.data,
    isLoading: sentiment.isLoading,
    isError: sentiment.isError,
    error: sentiment.error,

    // History
    history: history.data,
    historyLoading: history.isLoading,

    // Refresh
    refresh: refresh.mutate,
    isRefreshing: refresh.isPending,

    // Utils
    refetch: sentiment.refetch,
  };
}
