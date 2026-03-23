# Data Model: Fix Sentiment Overview & History Endpoints

**Date**: 2026-03-21
**Branch**: `1229-fix-sentiment-overview`

## Entities

### Sentiment Timeseries Bucket (existing — read-only for this feature)

**Table**: `{env}-sentiment-timeseries`
**PK**: `{ticker}#{resolution}` (e.g., `AAPL#24h`)
**SK**: ISO8601 bucket timestamp (e.g., `2026-03-21T00:00:00+00:00`)

| Attribute | Type | Description |
|-----------|------|-------------|
| PK | String | `{ticker}#{resolution}` |
| SK | String | ISO8601 bucket start timestamp |
| open | Number | First sentiment score in bucket |
| high | Number | Maximum sentiment score in bucket |
| low | Number | Minimum sentiment score in bucket |
| close | Number | Latest sentiment score in bucket |
| count | Number | Number of articles in bucket |
| sum | Number | Sum of all scores |
| avg | Number | Calculated average (sum/count) |
| label_counts | Map | Distribution: `{"positive": N, "neutral": N, "negative": N}` |
| sources | List[String] | Source attributions (e.g., `["tiingo:91120376"]`) |
| is_partial | Boolean | True if bucket time window hasn't ended |
| ttl | Number | Unix timestamp for auto-expiration |

### Resolution (modified — 8→6 values)

| Value | Duration | TTL | OHLC Equivalent |
|-------|----------|-----|-----------------|
| `1m` | 60s | 6 hours | `1` |
| `5m` | 300s | 12 hours | `5` |
| `15m` (NEW) | 900s | 24 hours | `15` |
| `30m` (NEW) | 1800s | 3 days | `30` |
| `1h` | 3600s | 7 days | `60` |
| `24h` | 86400s | 90 days | `D` |

**Removed**: `10m` (24h TTL), `3h` (14d TTL), `6h` (30d TTL), `12h` (60d TTL)

### SourceSentiment (existing model — no changes)

```
score: float (-1.0 to 1.0)
label: "positive" | "negative" | "neutral"
confidence: float | None
updated_at: str (ISO8601)
```

### TickerSentimentData (existing model — no changes)

```
symbol: str
sentiment: dict[str, SourceSentiment]   # key = source name or "aggregated"
```

### SentimentResponse (existing model — no changes)

```
config_id: str
tickers: list[TickerSentimentData]
last_updated: str (ISO8601)
next_refresh_at: str (ISO8601)
cache_status: "fresh" | "stale" | "refreshing"
```

## Data Flow

### Overview Endpoint

```
Request: GET /api/v2/configurations/{id}/sentiment?resolution=24h
    │
    ├── 1. Validate user owns configuration, extract tickers
    │
    ├── 2. For each ticker in configuration:
    │       query_timeseries(ticker, resolution, start=now-resolution, end=now)
    │       → TimeseriesResponse with buckets + partial_bucket
    │
    ├── 3. Transform latest bucket → SourceSentiment:
    │       bucket.avg → score
    │       score_to_label(score) → label
    │       bucket.count context → confidence
    │       bucket.timestamp → updated_at
    │
    ├── 4. Build TickerSentimentData per ticker:
    │       sentiment = {"aggregated": source_sentiment}
    │
    └── 5. Return SentimentResponse (cache result)
```

### History Endpoint

```
Request: GET /api/v2/configurations/{id}/sentiment/{ticker}/history?days=7&resolution=24h&source=tiingo
    │
    ├── 1. Validate user owns configuration, ticker is in config
    │
    ├── 2. query_timeseries(ticker, resolution, start=now-days, end=now)
    │       → TimeseriesResponse with all buckets in range
    │
    ├── 3. If source filter: keep only buckets where sources contains source prefix
    │
    ├── 4. Transform each bucket → time-series data point
    │
    └── 5. Return SentimentResponse with ticker history
```

## State Transitions

No state machines. The timeseries buckets are append-only (OHLC aggregation). The `is_partial` flag transitions from `true` to computed-`false` when the bucket's time window has elapsed.

## Validation Rules

- `resolution` parameter must be one of: `1m`, `5m`, `15m`, `30m`, `1h`, `24h`
- `days` parameter: 1–30 (existing validation)
- `source` parameter: `tiingo`, `finnhub`, or omitted (existing validation)
- Ticker must belong to the user's configuration (existing ownership check)
