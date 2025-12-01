'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchOHLCData, fetchSentimentHistory } from '@/lib/api/ohlc';
import { useAuthStore } from '@/stores/auth-store';
import type {
  TimeRange,
  ChartSentimentSource,
  OHLCResponse,
  SentimentHistoryResponse,
  ChartDataBundle,
} from '@/types/chart';
import { STALE_TIME_MS } from '@/lib/constants';

interface UseChartDataOptions {
  ticker: string | null;
  timeRange?: TimeRange;
  sentimentSource?: ChartSentimentSource;
  enabled?: boolean;
}

/**
 * Hook to fetch OHLC price data for a ticker.
 */
export function useOHLCData(ticker: string | null, timeRange: TimeRange = '1M') {
  const userId = useAuthStore((state) => state.user?.userId);

  return useQuery<OHLCResponse>({
    queryKey: ['ohlc', ticker, timeRange],
    queryFn: () => fetchOHLCData(ticker!, { range: timeRange }, userId!),
    enabled: !!ticker && !!userId,
    staleTime: STALE_TIME_MS,
  });
}

/**
 * Hook to fetch sentiment history for a ticker.
 */
export function useSentimentHistoryData(
  ticker: string | null,
  timeRange: TimeRange = '1M',
  source: ChartSentimentSource = 'aggregated'
) {
  const userId = useAuthStore((state) => state.user?.userId);

  return useQuery<SentimentHistoryResponse>({
    queryKey: ['sentiment-history-chart', ticker, timeRange, source],
    queryFn: () =>
      fetchSentimentHistory(ticker!, { range: timeRange, source }, userId!),
    enabled: !!ticker && !!userId,
    staleTime: STALE_TIME_MS,
  });
}

/**
 * Combined hook for price-sentiment chart data.
 *
 * Fetches both OHLC and sentiment history in parallel and combines them
 * into a single ChartDataBundle for the overlay chart component.
 */
export function useChartData({
  ticker,
  timeRange = '1M',
  sentimentSource = 'aggregated',
  enabled = true,
}: UseChartDataOptions): ChartDataBundle & {
  refetch: () => void;
  isStale: boolean;
} {
  const userId = useAuthStore((state) => state.user?.userId);

  const ohlcQuery = useQuery<OHLCResponse>({
    queryKey: ['ohlc', ticker, timeRange],
    queryFn: () => fetchOHLCData(ticker!, { range: timeRange }, userId!),
    enabled: enabled && !!ticker && !!userId,
    staleTime: STALE_TIME_MS,
  });

  const sentimentQuery = useQuery<SentimentHistoryResponse>({
    queryKey: ['sentiment-history-chart', ticker, timeRange, sentimentSource],
    queryFn: () =>
      fetchSentimentHistory(ticker!, { range: timeRange, source: sentimentSource }, userId!),
    enabled: enabled && !!ticker && !!userId,
    staleTime: STALE_TIME_MS,
  });

  const isLoading = ohlcQuery.isLoading || sentimentQuery.isLoading;
  const error =
    ohlcQuery.error?.message ||
    sentimentQuery.error?.message ||
    null;

  return {
    ticker: ticker || '',
    priceData: ohlcQuery.data?.candles || [],
    sentimentData: sentimentQuery.data?.history || [],
    timeRange,
    sentimentSource,
    isLoading,
    error,
    refetch: () => {
      ohlcQuery.refetch();
      sentimentQuery.refetch();
    },
    isStale: ohlcQuery.isStale || sentimentQuery.isStale,
  };
}
