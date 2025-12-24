# Spec: Dashboard OHLC Integration

**Feature ID**: 1038
**Priority**: P0 (Demo-critical)
**Status**: Draft

## Problem Statement

The main dashboard page (`frontend/src/app/(dashboard)/page.tsx`) currently uses `SentimentChart` with **mock data**, while `PriceSentimentChart` with full OHLC resolution selector and real API data exists but is not integrated into any user-facing route.

**Current State**:
- `SentimentChart`: Mock data, sentiment-only, no resolution selector
- `PriceSentimentChart`: Real OHLC data from Tiingo/Finnhub, 6 resolution options (1m, 5m, 15m, 30m, 1h, D), time range selector, sentiment overlay

**Goal**: Replace mock sentiment chart with real OHLC chart to make dashboard demo-able.

## User Stories

### US1: View Real OHLC Candles on Dashboard (P0)
**As a** demo viewer
**I want to** see real candlestick data when I search for a ticker
**So that** the dashboard demonstrates real financial data analysis

**Acceptance Criteria**:
- When user searches for a ticker (e.g., AAPL), real OHLC data displays
- Default resolution is "D" (daily) per existing convention
- Chart shows candlesticks with price data from Tiingo/Finnhub

### US2: Select Time Resolution (P1)
**As a** trader
**I want to** select different time resolutions (1m, 5m, 15m, 30m, 1h, D)
**So that** I can analyze price patterns at different granularities

**Acceptance Criteria**:
- Resolution selector buttons visible above chart
- Clicking resolution triggers data refetch
- Resolution persists across ticker changes (sessionStorage)

### US3: View Synchronized Sentiment Overlay (P2)
**As an** analyst
**I want to** see sentiment line overlaid on price candles
**So that** I can correlate sentiment with price movements

**Acceptance Criteria**:
- Sentiment line displays on right Y-axis (-1 to +1)
- Both layers share time axis at selected resolution
- Crosshair shows aligned OHLC + sentiment values

## Technical Approach

### Changes Required

1. **Replace SentimentChart import with PriceSentimentChart** in `page.tsx`
2. **Remove mock data generation** (generateMockData function)
3. **Pass ticker to PriceSentimentChart** for real API calls
4. **Handle loading states** properly during API fetches

### Existing Components to Leverage

- `PriceSentimentChart` - Already fully implemented (Feature 1035)
- `useChartData` hook - Handles OHLC + sentiment fetching
- `fetchOHLCData` API client - Connects to `/api/v2/tickers/{ticker}/ohlc`

### API Endpoints (Already Working)

- `GET /api/v2/tickers/{ticker}/ohlc` - Returns OHLC candlestick data
- `GET /api/v2/tickers/{ticker}/sentiment/history` - Returns sentiment time series

## Out of Scope

- New API endpoints (all exist)
- New backend logic (all implemented in Feature 1035)
- New chart components (PriceSentimentChart exists)

## Dependencies

- Feature 1035 (OHLC Resolution Selector) - MERGED
- PR #486 (Dashboard ECR IAM) - MERGED

## Risks

- **Low**: This is primarily a frontend integration of existing components
- **Medium**: Potential layout issues when swapping chart components

## Success Metrics

- Dashboard displays real OHLC data for any valid ticker
- Resolution selector visible and functional
- No console errors or API failures
- Load time < 2s for initial chart render
