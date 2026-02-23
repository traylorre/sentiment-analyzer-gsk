# Data Model: Real-Time Multi-Resolution Sentiment Time-Series

**Feature**: 1009-realtime-multi-resolution
**Date**: 2025-12-21

## Entities

### SentimentBucket

A time-bounded aggregation of sentiment data for a single ticker at a specific resolution.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| PK | String | `{ticker}#{resolution}` | Required, pattern: `^[A-Z]+#(1m|5m|10m|1h|3h|6h|12h|24h)$` |
| SK | String | ISO8601 bucket start timestamp | Required, aligned to resolution boundary |
| open | Number | First sentiment score in bucket | -1.0 to 1.0 |
| high | Number | Maximum sentiment score in bucket | -1.0 to 1.0 |
| low | Number | Minimum sentiment score in bucket | -1.0 to 1.0 |
| close | Number | Last sentiment score in bucket | -1.0 to 1.0 |
| count | Number | Number of articles in bucket | >= 0 |
| sum | Number | Sum of all scores (for avg calculation) | Any float |
| label_counts | Map | Distribution by sentiment label | `{"positive": N, "neutral": N, "negative": N}` |
| sources | List | Unique sources in bucket | List of strings |
| last_updated | String | ISO8601 timestamp of last update | Required |
| is_partial | Boolean | True if bucket is incomplete | Default: false |
| ttl | Number | TTL timestamp (epoch seconds) | Required, resolution-dependent |

### Resolution

Enumeration of supported time resolutions.

| Value | Display | Bucket Duration | TTL |
|-------|---------|-----------------|-----|
| 1m | 1 minute | 60 seconds | 6 hours |
| 5m | 5 minutes | 300 seconds | 12 hours |
| 10m | 10 minutes | 600 seconds | 24 hours |
| 1h | 1 hour | 3600 seconds | 7 days |
| 3h | 3 hours | 10800 seconds | 14 days |
| 6h | 6 hours | 21600 seconds | 30 days |
| 12h | 12 hours | 43200 seconds | 60 days |
| 24h | 24 hours | 86400 seconds | 90 days |

### PartialBucket

Extends SentimentBucket with progress information for the current incomplete bucket.

| Field | Type | Description |
|-------|------|-------------|
| (all SentimentBucket fields) | | |
| is_partial | Boolean | Always true |
| progress_pct | Number | 0-100, percentage through bucket period |
| next_update_at | String | ISO8601 timestamp when bucket completes |

### TickerSubscription

Connection state for SSE streaming.

| Field | Type | Description |
|-------|------|-------------|
| connection_id | String | UUID for the SSE connection |
| user_id | String | Optional authenticated user ID |
| resolutions | List | Resolutions to receive updates for |
| tickers | List | Tickers to filter (empty = all) |
| last_event_id | String | For reconnection support |
| connected_at | String | ISO8601 timestamp |

## DynamoDB Table Schema

### Table: `{env}-sentiment-timeseries`

```
Primary Key:
  PK (HASH): String - "{ticker}#{resolution}"
  SK (RANGE): String - ISO8601 bucket timestamp

Attributes:
  open: Number
  high: Number
  low: Number
  close: Number
  count: Number
  sum: Number
  label_counts: Map
  sources: List
  last_updated: String
  is_partial: Boolean
  ttl: Number (DynamoDB TTL enabled)

Capacity: On-Demand (PAY_PER_REQUEST)

No GSIs required (single-partition queries only)
```

### Access Patterns

| Pattern | Query | Expected Items |
|---------|-------|----------------|
| Get ticker at resolution | PK = "AAPL#1m", SK BETWEEN start AND end | 60-1440 |
| Get latest bucket | PK = "AAPL#5m", SK >= now - resolution, Limit 1, ScanIndexForward=false | 1 |
| Get partial bucket | Same as latest, filter is_partial=true | 0-1 |

## Bucket Alignment Rules

Buckets MUST align to consistent boundaries:

| Resolution | Alignment Rule | Examples |
|------------|---------------|----------|
| 1m | :00 seconds | 10:35:00, 10:36:00, 10:37:00 |
| 5m | :00, :05, :10, :15, :20, :25, :30, :35, :40, :45, :50, :55 | 10:35:00, 10:40:00 |
| 10m | :00, :10, :20, :30, :40, :50 | 10:30:00, 10:40:00 |
| 1h | :00 minutes | 10:00:00, 11:00:00 |
| 3h | 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00 | 09:00:00, 12:00:00 |
| 6h | 00:00, 06:00, 12:00, 18:00 | 06:00:00, 12:00:00 |
| 12h | 00:00, 12:00 | 00:00:00, 12:00:00 |
| 24h | 00:00 | 00:00:00 |

All times are UTC.

## State Transitions

### SentimentBucket Lifecycle

```
[Empty] → [Partial] → [Complete] → [Expired]
   │          │            │           │
   └──────────┴────────────┴───────────┘
           Article ingested
```

1. **Empty**: No articles yet in bucket (bucket not created)
2. **Partial**: Articles exist, bucket period not complete (`is_partial=true`)
3. **Complete**: Bucket period has passed (`is_partial=false`)
4. **Expired**: TTL reached, DynamoDB auto-deletes

### Write Operations

1. **Insert new bucket** (first article in time window):
   - Create with `is_partial=true`
   - Set OHLC values to article score
   - count=1, sum=score

2. **Update existing bucket** (subsequent articles):
   - Conditional update on PK+SK exists
   - Update high/low if score exceeds bounds
   - Set close to current score
   - Increment count, add to sum
   - Update label_counts
   - Add source to sources list (if not present)

3. **Finalize bucket** (scheduled every 5 minutes):
   - Query all buckets where `is_partial=true` AND SK < now - resolution
   - Set `is_partial=false`

## Validation Rules

1. **Ticker**: Must match configured tickers list (currently 13)
2. **Resolution**: Must be one of 8 supported values
3. **Timestamp alignment**: SK must align to resolution boundary
4. **Score range**: All score values must be -1.0 to 1.0
5. **Count consistency**: `count` must equal sum of `label_counts` values
6. **TTL validity**: TTL must be > last_updated
