# Feature Specification: E2E Cached Data Mock

**Feature Branch**: `1276-e2e-cached-data-mock`
**Created**: 2026-03-28
**Status**: Draft
**Input**: User description: "Three cached data Playwright tests timeout at ~17s because they search for AAPL against the mock API server which is slow. Fix by intercepting API calls with pre-canned data."

## Problem Analysis

Three Playwright E2E tests in the chaos test suite timeout because their `beforeEach` hooks perform a full search-select-wait-for-chart flow against the mock API server (`run-local-api.py`). The mock server proxies to Tiingo/Finnhub APIs for OHLC data, making each test spend 15-17s just loading data before the actual chaos assertions begin.

**Failing tests** (all timeout at ~17s):
- `chaos-cached-data.spec.ts`: "previously loaded data remains visible during API outage" (16.7s)
- `chaos-cached-data.spec.ts`: "cached data survives API timeout" (16.8s)
- `chaos-cross-browser.spec.ts`: "cached data persists during API outage" (17.9s)

**Root cause**: The OHLC endpoint in the mock server calls external Tiingo/Finnhub APIs (or generates slow mock data), making the chart data wait (`timeout: 15000`) consume nearly the entire test budget. The chaos tests don't test data loading -- they test that *already-loaded data persists* during API outages.

**Why sanity.spec.ts passes**: Same search+select pattern but uses Playwright's default 30s test timeout, giving enough headroom for the 10s search wait + 15s chart wait.

## Approach Decision

**Selected: Option 1 -- Mock search and OHLC APIs in-test with `page.route()`**

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| 1. `page.route()` mock | Fast (<1s), deterministic, no server dependency | Must maintain mock payloads | **Selected** |
| 2. Increase timeout | Zero code change | Papers over root issue, still slow CI | Rejected |
| 3. URL-based ticker state | Skip search entirely | Dashboard has no URL state support | Not feasible |

Approach 1 is the right fix because:
- Chaos tests verify cache resilience, not data fetching
- Mock data eliminates external API dependency (Tiingo/Finnhub)
- Tests become deterministic and fast (<2s data loading vs ~15s)
- Same `page.route()` pattern already used by `chaos-helpers.ts` (blockAllApi, triggerHealthBanner)

## User Scenarios & Testing

### User Story 1 - Fast Chaos Data Loading (Priority: P1)

The `beforeEach` in chaos-cached-data.spec.ts and the data loading in chaos-cross-browser.spec.ts should use `page.route()` to intercept:
1. `GET /api/v2/tickers/search?q=AAPL` -- return pre-canned search results
2. `GET /api/v2/tickers/AAPL/ohlc` -- return pre-canned OHLC candle data
3. `GET /api/v2/tickers/AAPL/sentiment/history` -- return pre-canned sentiment data

After intercepting, the existing search-select-wait-for-chart flow completes in <2s because responses are instant.

**Why this priority**: These three tests are the only failing tests in the chaos suite. Fixing them unblocks the PR.

**Independent Test**: Run `npx playwright test chaos-cached-data chaos-cross-browser --project="Desktop Chrome"` and verify all tests pass within 5s each.

**Acceptance Scenarios**:

1. **Given** chaos-cached-data tests run with mocked APIs, **When** the `beforeEach` completes, **Then** chart container has `aria-label` matching `/[1-9]\d* price candles/` within 3 seconds
2. **Given** chaos-cross-browser "cached data" test runs with mocked APIs, **When** data loads, **Then** the test completes in under 5 seconds total
3. **Given** mocked search response returns AAPL, **When** user types "AAPL" in search, **Then** the suggestion appears immediately and is clickable

---

### User Story 2 - Shared Mock Fixture (Priority: P2)

Extract the pre-canned API responses into a shared helper (`chaos-helpers.ts` or a new `mock-data.ts`) so that:
- Mock data is defined once, not duplicated across test files
- Other chaos tests can reuse the same pattern if needed
- Mock data structure matches the actual API contract (OHLCResponse, TickerSearchResponse, SentimentHistoryResponse)

**Why this priority**: Code quality -- prevents duplication and ensures maintainability.

**Independent Test**: Import the mock helper in any test file and verify it returns valid-shaped data.

**Acceptance Scenarios**:

1. **Given** a shared mock helper exists, **When** both chaos-cached-data and chaos-cross-browser import it, **Then** they use the same mock data definitions
2. **Given** mock data shapes, **When** compared to actual API response types, **Then** they include all required fields (symbol, candles, open/high/low/close/volume, timestamp)

---

### Edge Cases

- Mock OHLC data must include enough candles that `aria-label` matches `/[1-9]\d* price candles/` (at least 1 candle)
- Mock sentiment data must include enough points that `aria-label` matches `/[1-9]\d* sentiment points/` if tests check for it
- The `page.route()` interceptions must be set up BEFORE `page.goto('/')` to catch the initial page load requests, OR set up after navigation but before the search interaction
- Route interceptions must not interfere with the chaos injection phase (blockAllApi) -- the mock routes should be unrouted or the chaos routes should override them

## Requirements

### Functional Requirements

- **FR-001**: Chaos cached-data tests MUST complete each test (including beforeEach) in under 10 seconds total
- **FR-002**: Mock data MUST include valid OHLC candles with non-zero counts (matching existing aria-label assertions)
- **FR-003**: Mock data MUST include valid sentiment points with non-zero counts
- **FR-004**: Route interceptions for mock data MUST NOT interfere with subsequent chaos injection (`blockAllApi`, `page.route('**/api/**', ...)`)
- **FR-005**: Mock search response MUST return results matching `{ results: [{ symbol: "AAPL", name: "Apple Inc", exchange: "NASDAQ" }] }`
- **FR-006**: Mock OHLC response MUST return `{ candles: [...], ticker: "AAPL", range: "1M", resolution: "D" }` shape
- **FR-007**: Mock sentiment response MUST return `{ history: [...] }` shape

### Key Entities

- **MockTickerSearchResponse**: Pre-canned `/api/v2/tickers/search` response with AAPL result
- **MockOHLCResponse**: Pre-canned `/api/v2/tickers/AAPL/ohlc` response with 20+ candles
- **MockSentimentHistoryResponse**: Pre-canned `/api/v2/tickers/AAPL/sentiment/history` response with 10+ points

## Success Criteria

### Measurable Outcomes

- **SC-001**: All three failing tests pass consistently (0 flakes across 5 consecutive runs)
- **SC-002**: Each test completes in under 10 seconds (down from 17s)
- **SC-003**: No other chaos tests are broken by the change
- **SC-004**: Mock data is defined in a single shared location (no duplication)
