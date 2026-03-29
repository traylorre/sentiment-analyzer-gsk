# Implementation Plan: E2E Cached Data Mock

**Branch**: `1276-e2e-cached-data-mock` | **Date**: 2026-03-28 | **Spec**: `specs/1276-e2e-cached-data-mock/spec.md`

## Summary

Three chaos Playwright tests timeout (~17s) because they load real OHLC data through the mock API server, which calls external Tiingo/Finnhub APIs. The fix uses `page.route()` to intercept search, OHLC, and sentiment API calls with pre-canned responses, making data loading instant and deterministic. The chaos tests only need data to *exist* in the DOM -- they don't test data fetching correctness.

## Technical Context

**Language/Version**: TypeScript (Playwright test files)
**Primary Dependencies**: `@playwright/test ^1.57.0` (existing)
**Storage**: N/A
**Testing**: Playwright E2E tests (existing)
**Target Platform**: Node.js 18+ (Playwright runner)
**Project Type**: Web app (frontend/tests/e2e/)
**Performance Goals**: Each test completes in <10s (down from 17s)
**Constraints**: Must not break other chaos tests or sanity tests

## Constitution Check

- No new dependencies added -- PASS
- No infrastructure changes -- PASS
- No production code changes -- PASS (test-only)
- Uses existing `page.route()` pattern from chaos-helpers.ts -- PASS

## Design

### Mock Data Helper

Create a new file `frontend/tests/e2e/helpers/mock-api-data.ts` containing:

1. **`MOCK_TICKER_SEARCH_RESPONSE`**: Pre-canned response for `/api/v2/tickers/search?q=AAPL`
2. **`MOCK_OHLC_RESPONSE`**: Pre-canned OHLC candle data for `/api/v2/tickers/AAPL/ohlc` with 20 candles
3. **`MOCK_SENTIMENT_RESPONSE`**: Pre-canned sentiment history for `/api/v2/tickers/AAPL/sentiment/history` with 15 points
4. **`mockTickerDataApis(page)`**: Function that sets up `page.route()` interceptions for all three endpoints, returning an unroute function

### Route Interception Strategy

The mock routes intercept only the specific data-loading endpoints:
- `**/api/v2/tickers/search**` -- returns instant search results
- `**/api/v2/tickers/AAPL/ohlc**` -- returns instant OHLC data
- `**/api/v2/tickers/AAPL/sentiment/history**` -- returns instant sentiment data

When `blockAllApi(page, 503)` is called later in the test, it uses `**/api/**` which overlaps. Playwright routes are matched in LIFO (last registered wins) order, so `blockAllApi` registered AFTER the mock routes will take precedence for all API calls. This is the correct behavior: data loads fast via mocks, then chaos injection blocks everything.

### Changes to Test Files

**`chaos-cached-data.spec.ts`**:
- Import `mockTickerDataApis` from `./helpers/mock-api-data`
- In `beforeEach`, call `mockTickerDataApis(page)` before `page.goto('/')`
- Reduce the chart wait timeout from 15000 to 5000 (data is instant now)

**`chaos-cross-browser.spec.ts`**:
- Import `mockTickerDataApis` from `./helpers/mock-api-data`
- In the "cached data persists" test, call `mockTickerDataApis(page)` before search interaction
- Reduce the chart wait timeout from 15000 to 5000

## Source Code Structure

```text
frontend/tests/e2e/
├── helpers/
│   ├── chaos-helpers.ts          # Existing -- unchanged
│   └── mock-api-data.ts          # NEW -- shared mock data + route interception
├── chaos-cached-data.spec.ts     # MODIFIED -- use mockTickerDataApis
└── chaos-cross-browser.spec.ts   # MODIFIED -- use mockTickerDataApis
```

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Mock data shape diverges from real API | Mock shapes copy from actual TypeScript types (OHLCResponse, SentimentHistoryResponse) |
| Route interception conflicts with chaos injection | Playwright LIFO route matching ensures later blockAllApi takes precedence |
| Reduced timeouts cause flakes on slow CI | 5000ms is still generous for instant mock responses |
