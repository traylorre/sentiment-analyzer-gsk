export type SentimentLabel = 'positive' | 'neutral' | 'negative';

export interface SentimentScore {
  score: number;              // -1.0 to 1.0
  label: SentimentLabel;
  confidence: number;         // 0.0 to 1.0
  updatedAt: string;          // ISO 8601
}

export interface TickerSentiment {
  symbol: string;
  sentiment: {
    tiingo: SentimentScore;
    finnhub: SentimentScore;
    ourModel: SentimentScore;
  };
}

export interface SentimentData {
  configId: string;
  tickers: TickerSentiment[];
  lastUpdated: string;
  nextRefreshAt: string;
  cacheStatus: 'fresh' | 'stale' | 'error';
}

export interface SentimentTimeSeries {
  timestamp: string;
  score: number;
  source: 'tiingo' | 'finnhub' | 'our_model';
  articleCount?: number;
}

export interface ATRData {
  timestamp: string;
  atr: number;
  ticker: string;
}

export type SentimentSource = 'tiingo' | 'finnhub' | 'our_model';
