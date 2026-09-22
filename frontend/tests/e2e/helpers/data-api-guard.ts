/**
 * Guard for tests that require real market data APIs (Tiingo/Finnhub).
 *
 * LOCAL MODE (no PREPROD_API_URL). The local API server (run-local-api.py)
 * starts without API keys because .env.local is not committed, so tests that
 * depend on real OHLC price data would time out waiting for candles that never
 * arrive. Here the guard probes the local server and skips cleanly.
 *
 * REMOTE MODE (PREPROD_API_URL set). Spec 1401 layer 1. The guard used to probe
 * a hardcoded http://127.0.0.1:8000 in every mode. Against preprod nothing is
 * listening there — playwright.config.ts drops its webServer block precisely
 * because the target is remote — so the probe always threw, the catch below set
 * available = false, and all 16 sanity.spec.ts tests skipped green. That was one
 * of the four layers making the preprod deploy gate incapable of failing.
 *
 * So in remote mode this guard DOES NOT SKIP. It probes the preprod API, and an
 * unavailable data API fails the test. On preprod, absent market data is a
 * defect the deploy gate exists to catch, not a local configuration note.
 *
 * The probe also no longer asserts a cause it did not establish. It used to
 * coerce any outcome — 500, auth regression, network blip, empty-but-200 — into
 * "APIs not configured". It now reports what it actually observed.
 */

import { type TestType } from '@playwright/test';

/**
 * Where to probe. PREPROD_API_URL is set by the deploy workflow's Playwright
 * step from the deploy-preprod job's api_url output; its absence means we are
 * running against the local server.
 */
const REMOTE_API_BASE = process.env.PREPROD_API_URL?.replace(/\/+$/, '') || '';
const IS_REMOTE = REMOTE_API_BASE !== '';
const API_BASE = IS_REMOTE ? REMOTE_API_BASE : 'http://127.0.0.1:8000';

/** The probe's outcome: whether data is available, and what was observed. */
interface ProbeResult {
  available: boolean;
  /** What actually happened, for the skip or failure message. */
  detail: string;
}

let _probe: ProbeResult | null = null;

/**
 * Probe the API to check whether real market data is being served.
 *
 * 1. Creates an anonymous session to get a valid auth token.
 * 2. Fetches a minimal OHLC request for AAPL with 1W range.
 * 3. If the response contains at least 1 candle, the APIs are available.
 *
 * Result is cached for the lifetime of the worker process.
 */
async function probeDataApis(): Promise<ProbeResult> {
  if (_probe !== null) return _probe;

  const record = (available: boolean, detail: string): ProbeResult => {
    _probe = { available, detail };
    return _probe;
  };

  try {
    // Step 1: Get an auth token via anonymous session
    const authRes = await fetch(`${API_BASE}/api/v2/auth/anonymous`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(10000),
    });

    if (authRes.status !== 201) {
      return record(
        false,
        `POST ${API_BASE}/api/v2/auth/anonymous returned ${authRes.status}, expected 201`,
      );
    }

    const authData = await authRes.json();
    const token = authData?.token;
    if (!token) {
      return record(
        false,
        `POST ${API_BASE}/api/v2/auth/anonymous returned 201 with no token in the body`,
      );
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
      return record(
        false,
        `GET ${API_BASE}/api/v2/tickers/AAPL/ohlc returned ${res.status}`,
      );
    }

    const data = await res.json();
    const candles = Array.isArray(data?.candles) ? data.candles.length : null;

    if (candles === null) {
      return record(
        false,
        `GET ${API_BASE}/api/v2/tickers/AAPL/ohlc returned 200 with no candles array`,
      );
    }
    if (candles === 0) {
      // The one outcome that genuinely means "no market data configured".
      return record(
        false,
        `GET ${API_BASE}/api/v2/tickers/AAPL/ohlc returned 200 with 0 candles ` +
          `(no market data provider configured)`,
      );
    }

    return record(true, `${candles} candles from ${API_BASE}`);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return record(false, `probe of ${API_BASE} threw: ${message}`);
  }
}

/**
 * Require real market data, or dispose of the test honestly.
 *
 * Remote mode: throws. A preprod deploy that cannot serve market data must fail
 * the gate (spec 1401 FR-006).
 * Local mode: skips, naming the observed cause rather than an assumed one.
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
  const { available, detail } = await probeDataApis();
  if (available) return;

  if (IS_REMOTE) {
    throw new Error(
      `Market data is unavailable on the deployed target and this test cannot ` +
        `be skipped there: ${detail}. ` +
        `Skipping green here is what let a real defect ship to preprod ` +
        `(spec 1401). Read the probe result above rather than restoring a skip.`,
    );
  }

  t.skip(
    true,
    `Real market data APIs not available against the local server: ${detail}. ` +
      `These tests require .env.local with valid TIINGO_API_KEY / FINNHUB_API_KEY.`,
  );
}
