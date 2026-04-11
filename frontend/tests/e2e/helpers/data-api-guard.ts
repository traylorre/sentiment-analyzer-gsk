/**
 * Guard for tests that require real market data APIs (Tiingo/Finnhub).
 *
 * In CI, the local API server (run-local-api.py) starts without API keys
 * because .env.local is not committed. Tests that depend on real OHLC
 * price data will time out waiting for chart candles that never arrive.
 *
 * This guard probes the OHLC endpoint once per worker process and caches
 * the result. Tests call `skipWithoutDataApis(test)` in beforeEach to
 * skip cleanly with a descriptive message instead of timing out after 15s.
 */

import { type TestType } from '@playwright/test';

const API_BASE = 'http://127.0.0.1:8000';
let _dataApisAvailable: boolean | null = null;

/**
 * Probe the local API to check if real market data APIs are configured.
 *
 * 1. Creates an anonymous session to get a valid auth token.
 * 2. Fetches a minimal OHLC request for AAPL with 1W range.
 * 3. If the response contains at least 1 candle, the APIs are available.
 *
 * Result is cached for the lifetime of the worker process.
 */
async function checkDataApisAvailable(): Promise<boolean> {
  if (_dataApisAvailable !== null) return _dataApisAvailable;

  try {
    // Step 1: Get an auth token via anonymous session
    const authRes = await fetch(`${API_BASE}/api/v2/auth/anonymous`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(10000),
    });

    if (authRes.status !== 201) {
      _dataApisAvailable = false;
      return false;
    }

    const authData = await authRes.json();
    const token = authData?.token;
    if (!token) {
      _dataApisAvailable = false;
      return false;
    }

    // Step 2: Probe the OHLC endpoint with the auth token
    const res = await fetch(
      `${API_BASE}/api/v2/tickers/AAPL/ohlc?time_range=1W&resolution=D`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(15000),
      },
    );

    if (!res.ok) {
      _dataApisAvailable = false;
      return false;
    }

    const data = await res.json();
    _dataApisAvailable =
      Array.isArray(data?.candles) && data.candles.length > 0;
  } catch {
    _dataApisAvailable = false;
  }

  return _dataApisAvailable;
}

/**
 * Skip the current test if real market data APIs are not available.
 *
 * Usage in test files:
 * ```ts
 * import { skipWithoutDataApis } from './helpers/data-api-guard';
 *
 * test.beforeEach(async () => {
 *   await skipWithoutDataApis(test);
 * });
 * ```
 */
export async function skipWithoutDataApis(
  t: TestType<any, any>,
): Promise<void> {
  const available = await checkDataApisAvailable();
  t.skip(
    !available,
    'Real market data APIs not configured (TIINGO_API_KEY / FINNHUB_API_KEY missing). ' +
      'These tests require .env.local with valid API keys. Skipped in CI.',
  );
}
