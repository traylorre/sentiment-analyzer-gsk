# Data Model: Fix Mock OHLC/Sentiment Data Format

## Entities

### OHLCResponse

Complete price data response returned by the OHLC API endpoint. Source of truth: `src/lambdas/shared/models/ohlc.py`.

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| ticker | string | No | Stock ticker symbol (e.g., "AAPL") |
| candles | PriceCandle[] | No | Array of OHLC price bars |
| time_range | string | No | Human-readable time range (e.g., "1D", "1W", "1M") |
| start_date | string | No | Start of data range (YYYY-MM-DD) |
| end_date | string | No | End of data range (YYYY-MM-DD) |
| count | number | No | Length of candles array. Invariant: `count === candles.length` |
| source | "tiingo" \| "finnhub" | No | Data provider that served this response |
| cache_expires_at | string | No | ISO 8601 datetime (UTC, Z suffix) when cached data expires |
| resolution | string | No | Candle resolution (e.g., "5min", "1hour", "1day") |
| resolution_fallback | boolean | No | Whether a fallback resolution was used |
| fallback_message | string \| null | Yes | Explanation if resolution fallback occurred, null otherwise |

### PriceCandle

Individual OHLC price bar within a response.

| Field | Type | Nullable | Constraints | Description |
|-------|------|----------|-------------|-------------|
| date | string | No | ISO 8601 datetime (Z suffix) for intraday, YYYY-MM-DD for daily | Candle timestamp |
| open | number | No | > 0 | Opening price |
| high | number | No | > 0, >= low | Highest price in period |
| low | number | No | > 0, <= high | Lowest price in period |
| close | number | No | > 0 | Closing price |
| volume | number \| null | Yes | >= 0 when present | Trade volume, null if unavailable |

### SentimentHistoryResponse

Complete sentiment history returned by the sentiment API endpoint. Source of truth: `src/lambdas/shared/models/sentiment_history.py`.

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| ticker | string | No | Stock ticker symbol (e.g., "AAPL") |
| source | string | No | Sentiment data source identifier |
| history | SentimentPoint[] | No | Array of sentiment measurements |
| start_date | string | No | Start of data range (YYYY-MM-DD) |
| end_date | string | No | End of data range (YYYY-MM-DD) |
| count | number | No | Length of history array. Invariant: `count === history.length` |

### SentimentPoint

Individual sentiment measurement within a response.

| Field | Type | Nullable | Constraints | Description |
|-------|------|----------|-------------|-------------|
| date | string | No | YYYY-MM-DD format | Measurement date |
| score | number | No | >= -1.0, <= 1.0 | Sentiment score |
| source | "tiingo" \| "finnhub" \| "our_model" \| "aggregated" | No | Valid enum value | Data source for this measurement |
| confidence | number \| null | Yes | >= 0.0, <= 1.0 when present | Confidence level, null if unavailable |
| label | "positive" \| "neutral" \| "negative" \| null | Yes | Valid enum value when present | Classified sentiment label, null if not classified |

## Relationships

- An OHLCResponse contains zero or more PriceCandles in its `candles` array.
- A SentimentHistoryResponse contains zero or more SentimentPoints in its `history` array.
- The `count` field on both response types is a derived field equal to the length of their respective arrays.

## Invariants

1. **Count consistency**: `response.count === response.candles.length` (OHLC) and `response.count === response.history.length` (sentiment).
2. **Price ordering**: For every PriceCandle, `high >= low`. Open and close may be any positive value.
3. **Score bounds**: For every SentimentPoint, `-1.0 <= score <= 1.0`.
4. **Confidence bounds**: When non-null, `0.0 <= confidence <= 1.0`.
5. **Date format**: Intraday candle dates are ISO 8601 datetime with `Z` suffix. Daily candle dates and all sentiment dates are `YYYY-MM-DD`.
6. **Empty response dates**: When `count === 0`, `start_date` and `end_date` reflect the requested range, not null.

## State Transitions

N/A -- mock data objects are immutable test fixtures.
