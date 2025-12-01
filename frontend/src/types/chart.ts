/**
 * Chart types for Price-Sentiment Overlay feature.
 */

/** Predefined time ranges for chart display */
export type TimeRange = '1W' | '1M' | '3M' | '6M' | '1Y';

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

/** Single day's OHLC price data */
export interface PriceCandle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

/** OHLC endpoint response */
export interface OHLCResponse {
  ticker: string;
  candles: PriceCandle[];
  time_range: string;
  start_date: string;
  end_date: string;
  count: number;
  source: 'tiingo' | 'finnhub';
  cache_expires_at: string;
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
  sentimentSource: ChartSentimentSource;
  isLoading: boolean;
  error: string | null;
}

/** Chart loading states */
export type ChartLoadingState = 'idle' | 'loading' | 'success' | 'error';
