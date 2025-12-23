/**
 * Chart types for Price-Sentiment Overlay feature.
 */

/** Predefined time ranges for chart display */
export type TimeRange = '1W' | '1M' | '3M' | '6M' | '1Y';

/** OHLC candlestick resolution (T010) */
export type OHLCResolution = '1' | '5' | '15' | '30' | '60' | 'D';

/** Available sentiment sources for chart overlay (includes aggregated) */
export type ChartSentimentSource = 'tiingo' | 'finnhub' | 'our_model' | 'aggregated';

/** Time range to days mapping */
export const TIME_RANGE_DAYS: Record<TimeRange, number> = {
  '1W': 7,
  '1M': 30,
  '3M': 90,
  '6M': 180,
  '1Y': 365,
};

/** Resolution to max days mapping (T010) */
export const RESOLUTION_MAX_DAYS: Record<OHLCResolution, number> = {
  '1': 7,
  '5': 30,
  '15': 90,
  '30': 90,
  '60': 180,
  'D': 365,
};

/** Resolution display labels (T010) */
export const RESOLUTION_LABELS: Record<OHLCResolution, string> = {
  '1': '1m',
  '5': '5m',
  '15': '15m',
  '30': '30m',
  '60': '1h',
  'D': 'Day',
};

/** Single day's OHLC price data */
export interface PriceCandle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

/** OHLC endpoint response (T012) */
export interface OHLCResponse {
  ticker: string;
  candles: PriceCandle[];
  time_range: string;
  start_date: string;
  end_date: string;
  count: number;
  source: 'tiingo' | 'finnhub';
  cache_expires_at: string;
  resolution: OHLCResolution;
  resolution_fallback: boolean;
  fallback_message: string | null;
}

/** Sentiment score for a specific date */
export interface SentimentPoint {
  date: string;
  score: number;
  source: ChartSentimentSource;
  confidence?: number;
  label?: 'positive' | 'neutral' | 'negative';
}

/** Sentiment history endpoint response */
export interface SentimentHistoryResponse {
  ticker: string;
  source: ChartSentimentSource;
  history: SentimentPoint[];
  start_date: string;
  end_date: string;
  count: number;
}

/** Combined chart data bundle for the overlay chart component */
export interface ChartDataBundle {
  ticker: string;
  priceData: PriceCandle[];
  sentimentData: SentimentPoint[];
  timeRange: TimeRange;
  resolution: OHLCResolution;
  sentimentSource: ChartSentimentSource;
  isLoading: boolean;
  error: string | null;
  resolutionFallback?: boolean;
  fallbackMessage?: string | null;
}

/** Chart loading states */
export type ChartLoadingState = 'idle' | 'loading' | 'success' | 'error';
