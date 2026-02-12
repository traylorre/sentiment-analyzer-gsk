# Data Model: Price-Sentiment Overlay Chart

**Feature**: 011-price-sentiment-overlay
**Date**: 2025-12-01

## Entities

### 1. PriceCandle (Backend)

Represents a single day's OHLC price data. Extends existing `OHLCCandle` from adapters.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| date | datetime | Required, trading day | UTC timestamp of the trading day |
| open | float | Required, > 0 | Opening price |
| high | float | Required, >= open, >= close | Highest price |
| low | float | Required, <= open, <= close | Lowest price |
| close | float | Required, > 0 | Closing price |
| volume | int | Optional, >= 0 | Trading volume |

**Validation Rules**:
- `high >= max(open, close)`
- `low <= min(open, close)`
- `date` must be a valid trading day (not weekend/holiday)

**Source**: Tiingo API (primary), Finnhub API (fallback)

---

### 2. SentimentPoint (Backend)

Represents sentiment score for a specific date and source.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| date | date | Required | Date of sentiment measurement |
| score | float | Required, -1.0 to 1.0 | Sentiment score |
| source | string | Required, enum | Source: tiingo, finnhub, our_model, aggregated |
| confidence | float | Optional, 0.0 to 1.0 | Model confidence (if applicable) |
| label | string | Optional, enum | positive, neutral, negative |

**Validation Rules**:
- `score` clamped to [-1.0, 1.0]
- `source` must be one of: `tiingo`, `finnhub`, `our_model`, `aggregated`

**Source**: Existing sentiment endpoint, extended with history

---

### 3. TimeRange (Enum)

Predefined time ranges for chart display.

| Value | Description | Days |
|-------|-------------|------|
| 1W | 1 Week | 7 |
| 1M | 1 Month | 30 |
| 3M | 3 Months | 90 |
| 6M | 6 Months | 180 |
| 1Y | 1 Year | 365 |

**Default**: `1M` (30 days)

---

### 4. OHLCResponse (API Response)

Response model for OHLC price data endpoint.

| Field | Type | Description |
|-------|------|-------------|
| ticker | string | Stock symbol (e.g., "AAPL") |
| candles | list[PriceCandle] | Array of OHLC candles, oldest first |
| time_range | TimeRange | Requested time range |
| start_date | date | First candle date |
| end_date | date | Last candle date |
| count | int | Number of candles returned |
| source | string | Data source used (tiingo or finnhub) |
| cache_expires_at | datetime | When cached data expires |

---

### 5. SentimentHistoryResponse (API Response)

Response model for historical sentiment data.

| Field | Type | Description |
|-------|------|-------------|
| ticker | string | Stock symbol |
| source | string | Selected sentiment source |
| history | list[SentimentPoint] | Array of sentiment points, oldest first |
| start_date | date | First data point date |
| end_date | date | Last data point date |
| count | int | Number of points returned |

---

### 6. ChartDataBundle (Frontend)

Combined data structure for the overlay chart component.

| Field | Type | Description |
|-------|------|-------------|
| ticker | string | Stock symbol |
| priceData | CandlestickData[] | TradingView candlestick format |
| sentimentData | LineData[] | TradingView line series format |
| timeRange | TimeRange | Current time range |
| sentimentSource | string | Current sentiment source |
| isLoading | boolean | Loading state |
| error | string | null | Error message if failed |

**TradingView Data Formats**:
```typescript
// CandlestickData (from lightweight-charts)
interface CandlestickData {
  time: Time;  // Unix timestamp or YYYY-MM-DD string
  open: number;
  high: number;
  low: number;
  close: number;
}

// LineData (from lightweight-charts)
interface LineData {
  time: Time;
  value: number;  // Sentiment score -1 to 1
}
```

---

## Relationships

```
Configuration (USER#{user_id}, CONFIG#{config_id})
    │
    ├── has many → Tickers (string[])
    │                  │
    │                  └── fetches → PriceCandle[] (via Tiingo/Finnhub)
    │                  └── fetches → SentimentPoint[] (via sentiment endpoint)
    │
    └── ChartDataBundle (frontend aggregation)
            │
            ├── priceData: PriceCandle[] → CandlestickData[]
            └── sentimentData: SentimentPoint[] → LineData[]
```

---

## State Transitions

### Cache States

| State | Condition | Transition |
|-------|-----------|------------|
| FRESH | `now < cache_expires_at` | Return cached data |
| STALE | `now >= cache_expires_at` | Fetch new data, update cache |
| EMPTY | No cached data | Fetch from API |

### Chart Loading States

| State | Description | UI Behavior |
|-------|-------------|-------------|
| IDLE | No data requested | Show placeholder |
| LOADING | Fetching data | Show skeleton/spinner |
| SUCCESS | Data loaded | Render chart |
| ERROR | Fetch failed | Show error message with retry |

---

## Data Volume Estimates

| Time Range | Price Candles | Sentiment Points | Payload Size |
|------------|---------------|------------------|--------------|
| 1W | ~5 | ~7 | ~2 KB |
| 1M | ~22 | ~30 | ~8 KB |
| 3M | ~65 | ~90 | ~20 KB |
| 6M | ~130 | ~180 | ~40 KB |
| 1Y | ~252 | ~365 | ~80 KB |

*Note: Price candles only on trading days (~252/year), sentiment on all days.*

---

## Indexing Strategy

No new DynamoDB indexes required. OHLC data is fetched from external APIs and cached in-memory. Sentiment history uses existing GSI on timestamp.

**Cache Keys**:
- OHLC: `ohlc:{ticker}:{start_date}:{end_date}`
- Sentiment: `sentiment_history:{ticker}:{source}:{start_date}:{end_date}`
