'use client';

/**
 * Chart Data Hooks - Fetch OHLC and sentiment data for visualization.
 *
 * Feature 1165: Removed hydration dependencies.
 * Auth state now initializes immediately (memory-only store).
 */

import { useQuery } from '@tanstack/react-query';
import { fetchOHLCData, fetchSentimentHistory } from '@/lib/api/ohlc';
import { useAuthStore } from '@/stores/auth-store';
import type {
  TimeRange,
  OHLCResolution,
  ChartSentimentSource,
  OHLCResponse,
  SentimentHistoryResponse,
  ChartDataBundle,
} from '@/types/chart';
import { STALE_TIME_MS } from '@/lib/constants';

interface UseChartDataOptions {
  ticker: string | null;
  timeRange?: TimeRange;
  resolution?: OHLCResolution;
  sentimentSource?: ChartSentimentSource;
  enabled?: boolean;
}

/**
 * Hook to fetch OHLC price data for a ticker.
 * Supports resolution parameter for intraday data (T015-T017).
 *
 * Feature 1165: No hydration wait - memory-only store initializes immediately.
 */
export function useOHLCData(
  ticker: string | null,
  timeRange: TimeRange = '1M',
  resolution: OHLCResolution = 'D'
) {
  const userId = useAuthStore((state) => state.user?.userId);

  return useQuery<OHLCResponse>({
    queryKey: ['ohlc', ticker, timeRange, resolution],
    queryFn: () => fetchOHLCData(ticker!, { range: timeRange, resolution }, userId!),
    enabled: !!ticker && !!userId,
    staleTime: STALE_TIME_MS,
  });
}

/**
 * Hook to fetch sentiment history for a ticker.
 *
 * Feature 1165: No hydration wait - memory-only store initializes immediately.
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
 * Supports resolution parameter for intraday OHLC data (T015-T017).
 *
 * Feature 1165: No hydration wait - memory-only store initializes immediately.
 */
export function useChartData({
  ticker,
  timeRange = '1M',
  resolution = 'D',
  sentimentSource = 'aggregated',
  enabled = true,
}: UseChartDataOptions): ChartDataBundle & {
  refetch: () => void;
  isStale: boolean;
} {
  const userId = useAuthStore((state) => state.user?.userId);

  const ohlcQuery = useQuery<OHLCResponse>({
    queryKey: ['ohlc', ticker, timeRange, resolution],
    queryFn: () => fetchOHLCData(ticker!, { range: timeRange, resolution }, userId!),
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
    resolution: ohlcQuery.data?.resolution || resolution,
    sentimentSource,
    isLoading,
    error,
    resolutionFallback: ohlcQuery.data?.resolution_fallback,
    fallbackMessage: ohlcQuery.data?.fallback_message,
    refetch: () => {
      ohlcQuery.refetch();
      sentimentQuery.refetch();
    },
    isStale: ohlcQuery.isStale || sentimentQuery.isStale,
  };
}
