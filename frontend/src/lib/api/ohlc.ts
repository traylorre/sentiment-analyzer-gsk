/**
 * OHLC and Sentiment History API client for Price-Sentiment Overlay feature.
 */

import { api } from './client';
import type {
  OHLCResponse,
  SentimentHistoryResponse,
  TimeRange,
  OHLCResolution,
  ChartSentimentSource,
} from '@/types/chart';

interface OHLCParams {
  range?: TimeRange;
  resolution?: OHLCResolution;
  start_date?: string;
  end_date?: string;
}

interface SentimentHistoryParams {
  source?: ChartSentimentSource;
  range?: TimeRange;
  start_date?: string;
  end_date?: string;
}

/**
 * Fetch OHLC price data for a ticker.
 *
 * @param ticker - Stock ticker symbol (e.g., AAPL)
 * @param params - Query parameters for time range and resolution (T013-T014)
 * @param userId - User ID for authentication
 * @returns OHLCResponse with candles array
 */
export async function fetchOHLCData(
  ticker: string,
  params: OHLCParams = {},
  userId: string
): Promise<OHLCResponse> {
  return api.get<OHLCResponse>(`/api/v2/tickers/${ticker}/ohlc`, {
    params: {
      range: params.range,
      resolution: params.resolution,
      start_date: params.start_date,
      end_date: params.end_date,
    },
    headers: {
      'X-User-ID': userId,
    },
  });
}

/**
 * Fetch sentiment history for a ticker.
 *
 * @param ticker - Stock ticker symbol (e.g., AAPL)
 * @param params - Query parameters for source and time range
 * @param userId - User ID for authentication
 * @returns SentimentHistoryResponse with history array
 */
export async function fetchSentimentHistory(
  ticker: string,
  params: SentimentHistoryParams = {},
  userId: string
): Promise<SentimentHistoryResponse> {
  return api.get<SentimentHistoryResponse>(`/api/v2/tickers/${ticker}/sentiment/history`, {
    params: {
      source: params.source || 'aggregated',
      range: params.range,
      start_date: params.start_date,
      end_date: params.end_date,
    },
    headers: {
      'X-User-ID': userId,
    },
  });
}

/**
 * OHLC API namespace for consistency with other API modules.
 */
export const ohlcApi = {
  getOHLC: fetchOHLCData,
  getSentimentHistory: fetchSentimentHistory,
};
