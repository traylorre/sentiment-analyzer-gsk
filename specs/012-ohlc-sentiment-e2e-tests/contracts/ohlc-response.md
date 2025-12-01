# API Contract: OHLC Response

**Endpoint**: `GET /api/v2/tickers/{ticker}/ohlc`
**Version**: v2
**Date**: 2025-12-01

## Request

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| ticker | string | Yes | Stock ticker symbol (1-5 uppercase letters) |

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| range | enum | No | 1M | Time range: 1W, 1M, 3M, 6M, 1Y |
| start_date | date | No | - | Custom start date (YYYY-MM-DD) |
| end_date | date | No | today | Custom end date (YYYY-MM-DD) |

### Headers

| Header | Type | Required | Description |
|--------|------|----------|-------------|
| X-User-ID | string | Yes | User identification |

## Response

### Success Response (200 OK)

```json
{
  "ticker": "AAPL",
  "candles": [
    {
      "date": "2024-11-01",
      "open": 237.45,
      "high": 239.12,
      "low": 236.80,
      "close": 238.67,
      "volume": 45678900
    }
  ],
  "time_range": "1M",
  "start_date": "2024-11-01",
  "end_date": "2024-11-29",
  "count": 21,
  "source": "tiingo",
  "cache_expires_at": "2024-12-02T14:30:00Z"
}
```

### Response Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| ticker | string | Yes | Normalized ticker symbol (uppercase) |
| candles | array[PriceCandle] | Yes | Array of OHLC candles, sorted by date ascending |
| time_range | string | Yes | Time range used (1W, 1M, 3M, 6M, 1Y, or "custom") |
| start_date | date | Yes | Date of first candle |
| end_date | date | Yes | Date of last candle |
| count | integer | Yes | Number of candles in array |
| source | enum | Yes | Data source used: "tiingo" or "finnhub" |
| cache_expires_at | datetime | Yes | When cached data expires (ISO 8601) |

### PriceCandle Schema

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| date | date | Yes | YYYY-MM-DD | Trading day date |
| open | float | Yes | > 0 | Opening price |
| high | float | Yes | >= max(open, close) | Highest price |
| low | float | Yes | <= min(open, close) | Lowest price |
| close | float | Yes | > 0 | Closing price |
| volume | integer | No | >= 0 | Trading volume |

### Error Responses

#### 400 Bad Request

```json
{
  "detail": "Invalid ticker symbol: ABC123. Must be 1-5 letters."
}
```

Returned when:
- Ticker contains non-letter characters
- Ticker is empty or > 5 characters
- start_date is after end_date

#### 401 Unauthorized

```json
{
  "detail": "Missing user identification"
}
```

Returned when:
- X-User-ID header is missing or empty

#### 404 Not Found

```json
{
  "detail": "No price data available for ZZZZ"
}
```

Returned when:
- No data available for ticker from any source
- Both Tiingo and Finnhub failed

## Business Rules

### Ticker Validation
- Ticker must be 1-5 uppercase letters (A-Z)
- Lowercase input is normalized to uppercase
- Leading/trailing whitespace is trimmed
- No digits, symbols, or special characters allowed

### Date Range Calculation
- If `start_date` and `end_date` provided: use custom range
- If only `range` provided: calculate from today
- Time range mappings:
  - 1W = 7 days
  - 1M = 30 days
  - 3M = 90 days
  - 6M = 180 days
  - 1Y = 365 days

### Data Source Fallback
1. Try Tiingo first (primary source)
2. If Tiingo fails or returns no data, try Finnhub
3. If both fail, return 404

### Candle Ordering
- Candles are sorted by date ascending (oldest first)
- Duplicate dates are deduplicated

### Cache Behavior
- `cache_expires_at` indicates next market open
- Data does not change during market hours
- Cache TTL based on market schedule

## Test Scenarios

### Happy Path
- Valid ticker with default range
- Valid ticker with each TimeRange value
- Valid ticker with custom date range
- Lowercase ticker normalization
- Ticker with whitespace

### Error Cases
- Missing X-User-ID header
- Empty X-User-ID header
- Invalid ticker (digits, symbols, too long)
- start_date after end_date
- Unknown/delisted ticker

### Edge Cases
- Single day range (start == end)
- Date before ticker IPO
- Future end date
- Very large date range
