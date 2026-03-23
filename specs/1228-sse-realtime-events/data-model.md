# Data Model: Wire SSE Real-Time Events

**Feature**: 1228-sse-realtime-events
**Date**: 2026-03-20

## Existing Entities (Read-Only)

### Sentiment Item (DynamoDB: sentiment_items)

| Field | Type | Description |
|-------|------|-------------|
| source_id | String (PK) | `dedup:{sha256}` — unique article identifier |
| timestamp | String (SK) | ISO8601 — article publish timestamp |
| sentiment | String | `positive` / `neutral` / `negative` |
| score | Decimal | 0.0–1.0 model confidence score |
| matched_tickers | List[String] | Tickers mentioned (e.g., ["AAPL", "MSFT"]) |
| status | String | `pending` / `analyzed` |
| model_version | String | e.g., "distilbert-v1.0" |
| sources | List[String] | Data sources (e.g., ["tiingo"]) |

**GSI**: `by_sentiment` (PK: sentiment, SK: timestamp, projection: ALL)

### Timeseries Bucket (DynamoDB: sentiment_timeseries)

| Field | Type | Description |
|-------|------|-------------|
| PK | String | `{ticker}#{resolution}` (e.g., "AAPL#5m") |
| SK | String | ISO8601 bucket start timestamp |
| open | Decimal | First score in bucket |
| close | Decimal | Most recent score in bucket |
| high | Decimal | Highest score in bucket |
| low | Decimal | Lowest score in bucket |
| count | Number | Articles in this bucket |
| sum | Decimal | Sum of scores (for average computation) |
| ttl | Number | Unix timestamp for auto-expiration |

**No GSI needed**: Direct `GetItem` by PK+SK is sufficient.

## New Internal Entities (In-Memory Only)

### TickerAggregate

Computed per-ticker aggregate from the sentiment items poll. Stored in-memory for change detection.

| Field | Type | Description |
|-------|------|-------------|
| ticker | String | Stock ticker symbol |
| score | float | Weighted average score across all items for this ticker |
| label | String | Majority sentiment label (positive/neutral/negative) |
| confidence | float | Average confidence across items |
| count | int | Total articles for this ticker |

### TickerAggregateSnapshot

Previous poll's per-ticker aggregates, used for change detection (FR-003).

| Field | Type | Description |
|-------|------|-------------|
| aggregates | Dict[str, TickerAggregate] | Ticker → aggregate mapping |
| is_baseline | bool | True if this was the first poll (no events emitted) |

### BucketSnapshot

Previous poll's timeseries bucket data, used for change detection (FR-004a).

| Field | Type | Description |
|-------|------|-------------|
| buckets | Dict[str, dict] | `{ticker}#{resolution}` → bucket OHLC data |
| is_baseline | bool | True if this was the first poll (no events emitted) |

## Event Payloads (SSE)

### sentiment_update Event

```json
{
  "event": "sentiment_update",
  "id": "evt_uuid",
  "data": {
    "ticker": "AAPL",
    "score": 0.847,
    "label": "positive",
    "confidence": 0.912,
    "source": "aggregate",
    "timestamp": "2026-03-20T15:30:00Z"
  }
}
```

### partial_bucket Event

```json
{
  "event": "partial_bucket",
  "id": "evt_uuid",
  "data": {
    "ticker": "AAPL",
    "resolution": "5m",
    "bucket": {
      "open": 0.75,
      "close": 0.85,
      "high": 0.92,
      "low": 0.68,
      "count": 3,
      "sum": 2.43
    },
    "progress_pct": 65.3,
    "is_partial": true,
    "timestamp": "2026-03-20T15:30:00Z",
    "origin_timestamp": "2026-03-20T15:30:00Z"
  }
}
```

## State Transitions

```
Lambda Cold Start
    │
    ▼
[First Poll] ──→ Establish baseline snapshots
    │               (no events emitted, FR-011)
    ▼
[Subsequent Polls] ──→ Compare current vs. snapshot
    │                      │
    ├── Sentiment changed ──→ Emit sentiment_update
    ├── Bucket changed    ──→ Emit partial_bucket (via debouncer)
    └── No changes        ──→ Only heartbeat/metrics as before
```
