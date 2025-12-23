# Research: OHLC Resolution Selector (Feature 1035)

**Date**: 2025-12-23
**Feature Branch**: `1035-ohlc-resolution-selector`

## Decisions Made

### Decision 1: Use Finnhub as primary data source for intraday OHLC
- **Rationale**: Tiingo only supports daily OHLC data. Finnhub's `/stock/candle` endpoint already supports intraday resolutions (1, 5, 15, 30, 60 minutes).
- **Alternatives Considered**:
  - Tiingo (rejected: no intraday support)
  - Alpha Vantage (rejected: not integrated, rate limits)
- **Risk**: Finnhub free tier has 60 calls/minute rate limit

### Decision 2: Create OHLCResolution enum separate from sentiment Resolution
- **Rationale**: Finnhub supports resolutions (1, 5, 15, 30, 60, D, W, M) that differ from the sentiment timeseries resolutions (1m, 5m, 10m, 1h, etc.). Creating a separate type prevents confusion and maps directly to Finnhub API values.
- **Alternatives Considered**:
  - Reuse sentiment Resolution enum (rejected: mismatched values, different purpose)
  - Use string literals only (rejected: no type safety, validation harder)

### Decision 3: UI pattern matches existing time range selector
- **Rationale**: PriceSentimentChart already has a working pattern for time range buttons. Resolution selector will use same visual pattern for consistency.
- **Alternatives Considered**:
  - Dropdown select (rejected: too many clicks)
  - Radio buttons (rejected: doesn't match existing UI)

### Decision 4: Session storage for preference persistence
- **Rationale**: Spec requires session-level persistence. Using localStorage or sessionStorage is lightweight and requires no backend changes.
- **Alternatives Considered**:
  - Backend storage (rejected: over-engineered for demo, requires auth)
  - No persistence (rejected: poor UX per spec requirements)

### Decision 5: Auto-limit time range based on resolution
- **Rationale**: 1-minute data for 1 year would be millions of candles. Apply intelligent limits:
  - 1m: max 7 days
  - 5m: max 30 days
  - 15m/30m: max 90 days
  - 1h: max 180 days
  - Daily: no limit
- **Alternatives Considered**:
  - No limits (rejected: performance issues, browser memory)
  - Fixed 1000 candle limit (rejected: different resolutions need different limits)

## Technical Findings

### Backend Stack
- **Python Version**: 3.13
- **Framework**: Lambda handlers with FastAPI-style routing
- **OHLC Endpoint**: `GET /api/v2/tickers/{ticker}/ohlc`
- **Current Finnhub Resolution**: Hardcoded to "D" at `src/lambdas/shared/adapters/finnhub.py:323`
- **Cache TTL**: 1 hour for OHLC data

### Frontend Stack
- **Framework**: React 18 + TypeScript 5 + Next.js 14.2
- **Chart Library**: lightweight-charts 5.0.9
- **State Management**: Zustand + React Query
- **Styling**: Tailwind CSS + Radix UI

### Finnhub API Resolution Support
| Resolution | Finnhub Value | Description |
|------------|---------------|-------------|
| 1 minute   | "1"           | Intraday    |
| 5 minutes  | "5"           | Intraday    |
| 15 minutes | "15"          | Intraday    |
| 30 minutes | "30"          | Intraday    |
| 1 hour     | "60"          | Intraday    |
| Daily      | "D"           | End of day  |

### Files to Modify

**Backend**:
1. `src/lambdas/shared/models/ohlc.py` - Add OHLCResolution enum
2. `src/lambdas/shared/adapters/finnhub.py` - Parameterize resolution in get_ohlc()
3. `src/lambdas/dashboard/ohlc.py` - Add resolution query parameter

**Frontend**:
1. `frontend/src/types/chart.ts` - Add OHLCResolution type
2. `frontend/src/lib/api/ohlc.ts` - Add resolution to API params
3. `frontend/src/hooks/use-chart-data.ts` - Accept resolution parameter
4. `frontend/src/components/charts/price-sentiment-chart.tsx` - Add resolution selector UI

### Existing Infrastructure to Reuse
- Resolution enum pattern from `src/lib/timeseries/models.py`
- Time range button UI pattern from PriceSentimentChart
- Cache key pattern from Finnhub adapter
- React Query pattern from useChartData hook

## Risk Mitigation

### Rate Limiting
- Finnhub free tier: 60 calls/minute
- Mitigation: Cache TTL adjustments (shorter for intraday to get fresh data, but still cached)
- Cache keys will include resolution to prevent conflicts

### Data Availability
- Intraday data may not be available for all tickers
- Mitigation: Graceful fallback to daily if intraday unavailable
- Display clear message when resolution unavailable

### Performance
- Large datasets at fine resolutions
- Mitigation: Auto-limit time range based on resolution
- Frontend pagination if needed (future enhancement)
