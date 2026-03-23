# SSE Event Contracts: Feature 1228

**Date**: 2026-03-20

## Event Types

### sentiment_update

**Trigger**: Per-ticker aggregate sentiment changes between polling cycles.
**Frequency**: At most once per ticker per polling cycle (5s).
**Filter**: Config-specific streams filter by `connection.ticker_filters`.

```
event: sentiment_update
id: evt_{uuid}
data: {"ticker":"AAPL","score":0.847,"label":"positive","confidence":0.912,"source":"aggregate","timestamp":"2026-03-20T15:30:00Z"}
```

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| ticker | string | Non-empty | Stock ticker symbol |
| score | float | [0.0, 1.0] | Weighted average sentiment score |
| label | string | positive/neutral/negative | Majority sentiment label |
| confidence | float | [0.0, 1.0] | Average model confidence |
| source | string | Always "aggregate" | Indicates aggregated data |
| timestamp | string | ISO8601 UTC | When the aggregate was computed |

### partial_bucket

**Trigger**: Timeseries bucket OHLC data changes between polling cycles.
**Frequency**: At most once per ticker/resolution per debounce interval (100ms).
**Filter**: Config-specific streams filter by `connection.ticker_filters`.

```
event: partial_bucket
id: evt_{uuid}
data: {"ticker":"AAPL","resolution":"5m","bucket":{"open":0.75,"close":0.85,"high":0.92,"low":0.68,"count":3,"sum":2.43},"progress_pct":65.3,"is_partial":true,"timestamp":"2026-03-20T15:30:00Z","origin_timestamp":"2026-03-20T15:30:00Z"}
```

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| ticker | string | Non-empty | Stock ticker symbol |
| resolution | string | 1m/5m/10m/1h/3h/6h/12h/24h | Bucket resolution |
| bucket | object | OHLC fields | Current bucket aggregates |
| bucket.open | float | [0.0, 1.0] | First score in bucket |
| bucket.close | float | [0.0, 1.0] | Most recent score |
| bucket.high | float | [0.0, 1.0] | Highest score |
| bucket.low | float | [0.0, 1.0] | Lowest score |
| bucket.count | int | >= 0 | Articles in bucket |
| bucket.sum | float | >= 0 | Sum of scores |
| progress_pct | float | [0.0, 100.0] | Elapsed % of bucket window |
| is_partial | bool | Always true | Identifies as in-progress |
| timestamp | string | ISO8601 UTC | When event was generated |
| origin_timestamp | string | ISO8601 UTC | When bucket data was created |

## Existing Events (unchanged)

### heartbeat
No changes. Every 30 seconds (configurable via SSE_HEARTBEAT_INTERVAL).

### metrics
No changes. Emitted when aggregate counts change between polling cycles.

### deadline
No changes. Emitted when Lambda timeout is approaching.

## Stream Endpoints

### Global Stream: `GET /api/v2/stream`
- Events: heartbeat, metrics, sentiment_update, partial_bucket
- Filtering: None (all events delivered)

### Config Stream: `GET /api/v2/configurations/{config_id}/stream`
- Events: heartbeat, metrics, sentiment_update, partial_bucket
- Filtering: `sentiment_update` and `partial_bucket` filtered by `connection.ticker_filters`
- Authentication: Required (user_token or session cookie)

## Backwards Compatibility

- Existing `heartbeat` and `metrics` events are unchanged
- New `sentiment_update` and `partial_bucket` events are additive — clients that don't handle them simply ignore unknown event types (per SSE spec)
- Frontend `use-sse.ts` already handles `sentiment_update` (invalidates React Query caches)
