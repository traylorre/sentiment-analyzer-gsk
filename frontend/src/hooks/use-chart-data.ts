'use client';

import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchOHLCData, fetchSentimentHistory } from '@/lib/api/ohlc';
import { useAuthStore, useHasHydrated } from '@/stores/auth-store';
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
 * FR-015: Hydration-aware - waits for zustand to rehydrate before enabling query.
 */
export function useOHLCData(
  ticker: string | null,
  timeRange: TimeRange = '1M',
  resolution: OHLCResolution = 'D'
) {
  // T027: Include hasHydrated in enabled check
  const hasHydrated = useHasHydrated();
  const userId = useAuthStore((state) => state.user?.userId);
  const prevUserIdRef = useRef<string | undefined>(undefined);

  const query = useQuery<OHLCResponse>({
    queryKey: ['ohlc', ticker, timeRange, resolution],
    queryFn: () => fetchOHLCData(ticker!, { range: timeRange, resolution }, userId!),
    // FR-015: Only enable after hydration AND when userId is available
    enabled: hasHydrated && !!ticker && !!userId,
    staleTime: STALE_TIME_MS,
  });

  // T028: Refetch when userId transitions from null to valid value after hydration
  useEffect(() => {
    if (hasHydrated && userId && !prevUserIdRef.current && query.data === undefined) {
      query.refetch();
    }
    prevUserIdRef.current = userId;
  }, [hasHydrated, userId, query]);

  return query;
}

/**
 * Hook to fetch sentiment history for a ticker.
 * FR-015: Hydration-aware - waits for zustand to rehydrate before enabling query.
 */
export function useSentimentHistoryData(
  ticker: string | null,
  timeRange: TimeRange = '1M',
  source: ChartSentimentSource = 'aggregated'
) {
  // T027: Include hasHydrated in enabled check
  const hasHydrated = useHasHydrated();
  const userId = useAuthStore((state) => state.user?.userId);
  const prevUserIdRef = useRef<string | undefined>(undefined);

  const query = useQuery<SentimentHistoryResponse>({
    queryKey: ['sentiment-history-chart', ticker, timeRange, source],
    queryFn: () =>
      fetchSentimentHistory(ticker!, { range: timeRange, source }, userId!),
    // FR-015: Only enable after hydration AND when userId is available
    enabled: hasHydrated && !!ticker && !!userId,
    staleTime: STALE_TIME_MS,
  });

  // T028: Refetch when userId transitions from null to valid value after hydration
  useEffect(() => {
    if (hasHydrated && userId && !prevUserIdRef.current && query.data === undefined) {
      query.refetch();
    }
    prevUserIdRef.current = userId;
  }, [hasHydrated, userId, query]);

  return query;
}

/**
 * Combined hook for price-sentiment chart data.
 *
 * Fetches both OHLC and sentiment history in parallel and combines them
 * into a single ChartDataBundle for the overlay chart component.
 * Supports resolution parameter for intraday OHLC data (T015-T017).
 * FR-015: Hydration-aware - waits for zustand to rehydrate before enabling queries.
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
  // T027: Include hasHydrated in enabled check
  const hasHydrated = useHasHydrated();
  const userId = useAuthStore((state) => state.user?.userId);
  const prevUserIdRef = useRef<string | undefined>(undefined);

  const ohlcQuery = useQuery<OHLCResponse>({
    queryKey: ['ohlc', ticker, timeRange, resolution],
    queryFn: () => fetchOHLCData(ticker!, { range: timeRange, resolution }, userId!),
    // FR-015: Only enable after hydration AND when userId is available
    enabled: hasHydrated && enabled && !!ticker && !!userId,
    staleTime: STALE_TIME_MS,
  });

  const sentimentQuery = useQuery<SentimentHistoryResponse>({
    queryKey: ['sentiment-history-chart', ticker, timeRange, sentimentSource],
    queryFn: () =>
      fetchSentimentHistory(ticker!, { range: timeRange, source: sentimentSource }, userId!),
    // FR-015: Only enable after hydration AND when userId is available
    enabled: hasHydrated && enabled && !!ticker && !!userId,
    staleTime: STALE_TIME_MS,
  });

  // T028: Refetch when userId transitions from null to valid value after hydration
  useEffect(() => {
    if (hasHydrated && userId && !prevUserIdRef.current) {
      if (ohlcQuery.data === undefined) ohlcQuery.refetch();
      if (sentimentQuery.data === undefined) sentimentQuery.refetch();
    }
    prevUserIdRef.current = userId;
  }, [hasHydrated, userId, ohlcQuery, sentimentQuery]);

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
