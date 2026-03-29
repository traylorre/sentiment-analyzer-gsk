// Target: Customer Dashboard (Next.js/Amplify)
/**
 * Pre-canned API response data for chaos tests (Feature 1276).
 *
 * Chaos cached-data tests verify that previously loaded data persists
 * during API outages. They don't test data fetching correctness.
 * Mocking the search/OHLC/sentiment APIs eliminates external API
 * dependency (Tiingo/Finnhub) and makes data loading instant (<1s).
 *
 * Shapes match the actual API contracts:
 * - TickerSearchResponse: src/lib/api/tickers.ts
 * - OHLCResponse: src/types/chart.ts
 * - SentimentHistoryResponse: src/types/chart.ts
 */

import type { Page } from '@playwright/test';

// ─── Mock Data ──────────────────────────────────────────────────────────────

/** Pre-canned search response for AAPL */
const MOCK_TICKER_SEARCH_RESPONSE = {
  results: [
    { symbol: 'AAPL', name: 'Apple Inc', exchange: 'NASDAQ' },
  ],
};

/** Generate N price candles starting from a base date */
function generateCandles(count: number): Array<{
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}> {
  const candles = [];
  const baseDate = new Date('2026-03-01');
  let price = 178.5;

  for (let i = 0; i < count; i++) {
    const date = new Date(baseDate);
    date.setDate(baseDate.getDate() + i);
    // Skip weekends
    if (date.getDay() === 0 || date.getDay() === 6) continue;

    const open = price;
    const high = price + Math.random() * 3;
    const low = price - Math.random() * 2;
    const close = low + Math.random() * (high - low);
    price = close;

    candles.push({
      date: date.toISOString().split('T')[0],
      open: Math.round(open * 100) / 100,
      high: Math.round(high * 100) / 100,
      low: Math.round(low * 100) / 100,
      close: Math.round(close * 100) / 100,
      // FR-009: At least one candle has null volume to exercise null-handling
      volume: i === 0 ? null : Math.floor(50_000_000 + Math.random() * 30_000_000),
    });
  }
  return candles;
}

/** Generate N sentiment points matching candle dates.
 * FR-008: Uses multiple source values for realistic coverage.
 * FR-009: First entry has null confidence and label to exercise null-handling.
 * Includes negative scores to exercise full [-1.0, 1.0] range.
 */
function generateSentimentPoints(
  count: number,
): Array<{
  date: string;
  score: number;
  source: 'tiingo' | 'finnhub' | 'our_model' | 'aggregated';
  confidence: number | null;
  label: 'positive' | 'neutral' | 'negative' | null;
}> {
  const sources = ['aggregated', 'our_model', 'tiingo', 'finnhub'] as const;
  const points = [];
  const baseDate = new Date('2026-03-01');

  for (let i = 0; i < count; i++) {
    const date = new Date(baseDate);
    date.setDate(baseDate.getDate() + i);
    if (date.getDay() === 0 || date.getDay() === 6) continue;

    // Include negative scores for range coverage (FR-007)
    const score = i === 1 ? -0.85 : 0.3 + Math.random() * 0.5;
    const roundedScore = Math.round(score * 1000) / 1000;

    // FR-009: First entry has null confidence and label
    const isNullVariant = i === 0;

    points.push({
      date: date.toISOString().split('T')[0],
      score: roundedScore,
      source: sources[i % sources.length],
      confidence: isNullVariant ? null : 0.85,
      label: isNullVariant
        ? null
        : roundedScore > 0.6
          ? 'positive'
          : roundedScore > 0.4
            ? 'neutral'
            : 'negative',
    });
  }
  return points;
}

// Pre-generate data so all tests get consistent shapes
const CANDLES = generateCandles(30);
const SENTIMENT_POINTS = generateSentimentPoints(30);

/** Pre-canned OHLC response for AAPL */
const MOCK_OHLC_RESPONSE = {
  ticker: 'AAPL',
  candles: CANDLES,
  time_range: '1M',
  start_date: CANDLES[0]?.date ?? '2026-03-01',
  end_date: CANDLES[CANDLES.length - 1]?.date ?? '2026-03-28',
  count: CANDLES.length,
  source: 'tiingo',
  cache_expires_at: new Date(Date.now() + 3600_000).toISOString(),
  resolution: 'D',
  resolution_fallback: false,
  fallback_message: null,
};

/** Pre-canned sentiment history response for AAPL */
const MOCK_SENTIMENT_RESPONSE = {
  ticker: 'AAPL',
  source: 'aggregated',
  history: SENTIMENT_POINTS,
  start_date: SENTIMENT_POINTS[0]?.date ?? '2026-03-01',
  end_date: SENTIMENT_POINTS[SENTIMENT_POINTS.length - 1]?.date ?? '2026-03-28',
  count: SENTIMENT_POINTS.length,
};

/** FR-012: Empty-array OHLC response variant for edge case testing */
export const MOCK_EMPTY_OHLC_RESPONSE = {
  ticker: 'AAPL',
  candles: [],
  time_range: '1M',
  start_date: '2026-03-01',
  end_date: '2026-03-28',
  count: 0,
  source: 'tiingo' as const,
  cache_expires_at: new Date(Date.now() + 3600_000).toISOString(),
  resolution: 'D',
  resolution_fallback: false,
  fallback_message: null,
};

/** FR-012: Empty-array sentiment response variant for edge case testing */
export const MOCK_EMPTY_SENTIMENT_RESPONSE = {
  ticker: 'AAPL',
  source: 'aggregated' as const,
  history: [],
  start_date: '2026-03-01',
  end_date: '2026-03-28',
  count: 0,
};

// ─── Route Interception ─────────────────────────────────────────────────────

/**
 * Set up page.route() interceptions for ticker search, OHLC, and sentiment
 * endpoints. Returns instantly with pre-canned data, bypassing external APIs.
 *
 * Call this BEFORE page.goto('/') or before the search interaction.
 *
 * When blockAllApi() is called later in the test, Playwright's LIFO route
 * matching ensures the broader `** /api/**` pattern takes precedence,
 * correctly simulating a full API outage for the chaos assertions.
 *
 * @returns A cleanup function that removes all mock routes
 */
export async function mockTickerDataApis(page: Page): Promise<() => Promise<void>> {
  // Mock anonymous auth — useChartData requires hasAccessToken=true
  await page.route('**/api/v2/auth/anonymous', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'mock-test-token',
        token_type: 'bearer',
        auth_type: 'anonymous',
        user_id: 'anon-test-user',
        session_expires_in_seconds: 3600,
      }),
    });
  });

  // Mock ticker search — match any search query
  await page.route('**/api/v2/tickers/search**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_TICKER_SEARCH_RESPONSE),
    }),
  );

  // Mock OHLC data — match any ticker's OHLC endpoint
  await page.route('**/api/v2/tickers/*/ohlc**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_OHLC_RESPONSE),
    }),
  );

  // Mock sentiment history — match any ticker's sentiment endpoint
  await page.route('**/api/v2/tickers/*/sentiment/history**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_SENTIMENT_RESPONSE),
    }),
  );

  return async () => {
    await page.unroute('**/api/v2/auth/anonymous');
    await page.unroute('**/api/v2/tickers/search**');
    await page.unroute('**/api/v2/tickers/*/ohlc**');
    await page.unroute('**/api/v2/tickers/*/sentiment/history**');
  };
}
