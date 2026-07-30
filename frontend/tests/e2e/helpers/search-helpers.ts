// Target: Customer Dashboard (Next.js/Amplify)
/**
 * Ticker-search helpers for E2E tests (Feature 001 — waitForResponse race sweep).
 *
 * Exists to make one ordering impossible to get wrong: the response listener must be registered
 * BEFORE the interaction that triggers the request. Registering it after leaves a window in which
 * the response can arrive unobserved, and the wait then blocks until its timeout — a race that
 * fails intermittently under load and passes on a quiet machine.
 *
 * Encapsulating the ordering means it cannot be reintroduced one call site at a time.
 */

import type { Locator, Page, Response } from '@playwright/test';

/** Options for {@link searchAndAwaitResponse}. */
export interface SearchAndAwaitOptions {
  /**
   * Response matcher. Passed through to `page.waitForResponse` **unmodified** (guarantee G3):
   * no wrapping, no `&&`, no widening. A caller supplying a predicate gets exactly that predicate.
   */
  predicate?: (response: Response) => boolean;
  /**
   * Wait budget in milliseconds. Defaults to 15000, deliberately below the 30s test-level timeout
   * so a failure names this wait rather than the whole test. Tests containing more than two
   * converted waits also need `test.setTimeout(60000)` for this cap to bind (FR-006).
   */
  timeout?: number;
  /** Fill `''` before filling the query. See the note on the empty fill below. */
  clearFirst?: boolean;
}

/**
 * The default matcher: URL-only, scoped to the ticker-search endpoint.
 *
 * This matches **13 of the 18** URL-scoped sites, not all 18. Five sites in
 * `chaos-degradation.spec.ts` are not covered:
 *
 * - `:131` and `:138` carry a status check (`=== 500`, `=== 200`). The default would drop it and
 *   WIDEN the match, which FR-002 forbids, so those sites MUST pass their original predicate.
 * - `:178`, `:183` and `:188` match `/tickers/search` without the `/api/v2` prefix. The default
 *   NARROWS those, which is permitted but must be declared by the converting task.
 *
 * See `specs/001-waitforresponse-race-sweep/contracts/helper-api.md`, "Sites requiring an explicit
 * predicate". An earlier draft claimed the default covered all 18; it does not.
 */
const DEFAULT_PREDICATE = (response: Response): boolean =>
  response.url().includes('/api/v2/tickers/search');

/** FR-006 / research D3. Below the 30s test-level timeout so failures name the wait. */
const DEFAULT_TIMEOUT_MS = 15000;

/**
 * Type a ticker query and await the resulting search response, listener-first.
 *
 * The response promise is created before any interaction with `searchInput` (guarantee G1). This
 * ordering is the entire point of the helper and MUST NOT be rearranged.
 *
 * Non-guarantees, so callers do not assume them:
 *
 * - **N1 — cache-served queries are not detected.** Repeating the same query inside React Query's
 *   30s `staleTime` window issues no request (`ticker-input.tsx:38`), so this will hang until
 *   `timeout`. Callers in that situation must assert on the UI instead; see
 *   `ticker-search-gaps.spec.ts` for the existing precedent. Enforced by FR-010, not by code.
 * - **N2 — a request and its retry are not disambiguated.** React Query is configured with
 *   `retry: 1` (`providers.tsx:48`). Where a prior interaction errored, supply a query-scoped
 *   predicate (FR-002 / research D4).
 * - **N3 — this helper is not for non-search waits.** The 9 status-only and `requestfailed` sites
 *   are converted inline instead (FR-005).
 *
 * @param page          The Playwright page.
 * @param searchInput   The ticker search input locator.
 * @param query         The text to type.
 * @param options       See {@link SearchAndAwaitOptions}.
 * @returns The matched `Response`.
 *
 * @example
 * // URL-scoped search site (the common case)
 * await searchAndAwaitResponse(page, searchInput, 'AAPL');
 *
 * @example
 * // Error-path site needing a query-scoped predicate (research D4)
 * await searchAndAwaitResponse(page, searchInput, 'GOOG', {
 *   clearFirst: true,
 *   predicate: (r) => r.url().includes('q=GOOG') && r.status() === 200,
 * });
 */
export async function searchAndAwaitResponse(
  page: Page,
  searchInput: Locator,
  query: string,
  options?: SearchAndAwaitOptions,
): Promise<Response> {
  const {
    predicate = DEFAULT_PREDICATE,
    timeout = DEFAULT_TIMEOUT_MS,
    clearFirst = false,
  } = options ?? {};

  // G1: registered before any interaction. Do not move this below the fills.
  // G3: `predicate` is passed through untouched.
  const responsePromise = page.waitForResponse(predicate, { timeout });

  // G2 (contract Option B — sink attached at creation). If `fill()` throws, control never reaches
  // the await below, and without this the listener would reject at `timeout` with nobody awaiting
  // it — surfacing as an unhandled rejection against whatever test happens to be running then.
  // Attaching the sink on the creation line means the promise is never unhandled regardless of
  // what happens after. The `return await` below still yields the real rejection to the caller.
  responsePromise.catch(() => {});

  if (clearFirst) {
    // Safe to bracket inside the single listener: an empty query never fetches, because the
    // ticker query is gated on `enabled: query.length >= 1` (`ticker-input.tsx:37`). Playwright
    // documents `locator.clear()` as equivalent to `fill('')`, so replacing an existing
    // `.clear()` with `clearFirst: true` is not a behaviour change.
    await searchInput.fill('');
  }
  await searchInput.fill(query);

  return await responsePromise;
}
