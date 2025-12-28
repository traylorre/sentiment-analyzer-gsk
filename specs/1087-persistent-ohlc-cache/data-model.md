# Data Model: Persistent OHLC Cache

**Feature**: 1087-persistent-ohlc-cache
**Date**: 2025-12-28

## Entities

### OHLCCacheItem (DynamoDB)

The persistent cache item stored in DynamoDB.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| PK | string | Partition key: `{ticker}#{source}` | Required, e.g., "AAPL#tiingo" |
| SK | string | Sort key: `{resolution}#{timestamp}` | Required, e.g., "5m#2025-12-27T10:30:00Z" |
| open | Decimal | Opening price | Required, precision 4 decimal places |
| high | Decimal | Highest price | Required, precision 4 decimal places |
| low | Decimal | Lowest price | Required, precision 4 decimal places |
| close | Decimal | Closing price | Required, precision 4 decimal places |
| volume | int | Trading volume | Optional, may be 0 for some sources |
| fetched_at | string | ISO8601 timestamp when fetched from API | Required |

**Key Design**:
```
PK: {ticker}#{source}     → Partition by symbol and data provider
SK: {resolution}#{ts}     → Sort by resolution then time for efficient range queries
```

**Access Patterns**:
1. Get candles for ticker+source+resolution in time range
2. Check if specific candle exists (cache hit check)

### OHLCCacheQuery (Pydantic Model)

Query parameters for cache lookup.

```python
class OHLCCacheQuery(BaseModel):
    ticker: str          # e.g., "AAPL"
    source: str          # "tiingo" | "finnhub"
    resolution: str      # "1m" | "5m" | "15m" | "30m" | "1h" | "D"
    start_time: datetime # Range start (inclusive)
    end_time: datetime   # Range end (inclusive)
```

### OHLCCacheResult (Pydantic Model)

Result from cache query.

```python
class OHLCCacheResult(BaseModel):
    candles: list[CachedCandle]  # Retrieved candles
    cache_hit: bool              # True if any data from cache
    missing_ranges: list[tuple[datetime, datetime]]  # Gaps needing API fetch
```

### CachedCandle (Pydantic Model)

Individual candle from cache.

```python
class CachedCandle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    source: str
    resolution: str
```

---

## DynamoDB Table Definition

### Table: `{env}-ohlc-cache`

```hcl
resource "aws_dynamodb_table" "ohlc_cache" {
  name         = "${var.environment}-ohlc-cache"
  billing_mode = "PAY_PER_REQUEST"  # On-demand for unpredictable workloads
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # No TTL for now - historical data is permanent
  # TTL cleanup deferred to future work per spec

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Feature = "1087-persistent-ohlc-cache"
  }
}
```

---

## State Transitions

### Cache Population Flow

```
EMPTY → FETCHING → POPULATED
         ↓
      FETCH_FAILED (graceful degradation)
```

| State | Description | Next States |
|-------|-------------|-------------|
| EMPTY | No data in cache for query | FETCHING |
| FETCHING | Calling external API | POPULATED, FETCH_FAILED |
| POPULATED | Data written to cache | (terminal) |
| FETCH_FAILED | API error, return empty gracefully | (terminal) |

---

## Validation Rules

### Ticker Validation
- Must be 1-5 uppercase letters (existing validation in ticker_cache.py)
- Must pass symbol validation against Tiingo/Finnhub

### Resolution Validation
- Must be one of: `1m`, `5m`, `15m`, `30m`, `1h`, `D`
- Maps to `OHLCResolution` enum in `src/lambdas/shared/models/ohlc.py`

### Timestamp Validation
- Must be ISO8601 format with timezone (UTC preferred)
- Start time must be before end time
- Time range must not exceed resolution-specific limits (existing in `RESOLUTION_MAX_DAYS`)

### Price Validation
- open, high, low, close must be positive floats
- high >= max(open, close)
- low <= min(open, close)
- volume >= 0

---

## Relationships

```
┌─────────────────┐
│   Dashboard     │
│   (ohlc.py)     │
└────────┬────────┘
         │ Query
         ▼
┌─────────────────┐
│   OHLCCache     │◄────── Write-through
│ (ohlc_cache.py) │
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐
│   Adapters      │
│ (tiingo.py,     │
│  finnhub.py)    │
└────────┬────────┘
         │ Fetch
         ▼
┌─────────────────┐
│  External APIs  │
│ (Tiingo,Finnhub)│
└─────────────────┘
```

---

## Sample Data

### DynamoDB Item Example

```json
{
  "PK": {"S": "AAPL#tiingo"},
  "SK": {"S": "5m#2025-12-27T10:30:00Z"},
  "open": {"N": "195.5000"},
  "high": {"N": "196.0000"},
  "low": {"N": "195.2500"},
  "close": {"N": "195.7500"},
  "volume": {"N": "1234567"},
  "fetched_at": {"S": "2025-12-27T10:35:00Z"}
}
```

### Query Response Example

```python
OHLCCacheResult(
    candles=[
        CachedCandle(timestamp=datetime(2025,12,27,10,30), open=195.50, high=196.00, low=195.25, close=195.75, volume=1234567, source="tiingo", resolution="5m"),
        CachedCandle(timestamp=datetime(2025,12,27,10,35), open=195.75, high=195.90, low=195.60, close=195.80, volume=987654, source="tiingo", resolution="5m"),
    ],
    cache_hit=True,
    missing_ranges=[]
)
```
