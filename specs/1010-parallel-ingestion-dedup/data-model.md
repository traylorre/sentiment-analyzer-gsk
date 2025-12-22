# Data Model: Parallel Ingestion with Cross-Source Deduplication

**Feature**: 1010-parallel-ingestion-dedup
**Date**: 2025-12-21

## Entities

### Article (Enhanced)

The core entity representing a unique news article identified by cross-source deduplication.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| source_id | string | Yes | Primary key: `dedup:{dedup_key}` |
| timestamp | string | Yes | Sort key: ISO8601 publish timestamp |
| dedup_key | string | Yes | 32-char SHA256 hex of normalized headline + date |
| headline | string | Yes | Display headline (from first source) |
| normalized_headline | string | Yes | Normalized headline used for dedup |
| sources | list[string] | Yes | Array of source names: ["tiingo", "finnhub"] |
| source_attribution | map | Yes | Per-source metadata (see SourceAttribution) |
| status | string | Yes | pending, analyzed, error |
| sentiment | string | No | positive, neutral, negative (after analysis) |
| score | float | No | Sentiment confidence 0.0-1.0 (after analysis) |
| matched_tickers | list[string] | Yes | Tickers this article relates to |
| text_for_analysis | string | No | Text snippet for ML inference |
| metadata | map | No | Additional article metadata |
| ttl_timestamp | number | Yes | Unix epoch for DynamoDB TTL (30 days) |
| created_at | string | Yes | ISO8601 timestamp of first ingestion |
| updated_at | string | Yes | ISO8601 timestamp of last update |

**Key Design**:
- PK: `source_id` = `dedup:{dedup_key}` (enables cross-source dedup)
- SK: `timestamp` (enables time-range queries)
- Dedup key ensures same article from different sources maps to same item

### SourceAttribution

Per-source metadata stored in the `source_attribution` map.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| article_id | string | Yes | Source-specific article identifier |
| url | string | Yes | Original article URL |
| crawl_timestamp | string | Yes | ISO8601 when source provided this article |
| original_headline | string | Yes | Headline as provided by source (before normalization) |
| source_name | string | No | Wire service name (e.g., "reuters", "ap") |

**Example**:
```json
{
  "tiingo": {
    "article_id": "91144751",
    "url": "https://www.fool.com.au/...",
    "crawl_timestamp": "2025-12-21T14:28:00Z",
    "original_headline": "Apple Reports Q4 Earnings Beat - Reuters",
    "source_name": "fool.com.au"
  },
  "finnhub": {
    "article_id": "abc-123-def",
    "url": "https://finnhub.io/...",
    "crawl_timestamp": "2025-12-21T14:29:00Z",
    "original_headline": "Apple reports Q4 earnings beat",
    "source_name": "reuters"
  }
}
```

### CollisionMetrics

Metrics recorded per ingestion run for monitoring dedup effectiveness.

| Field | Type | Description |
|-------|------|-------------|
| invocation_id | string | Lambda request ID |
| timestamp | string | ISO8601 invocation time |
| articles_fetched | map | Per-source fetch counts {"tiingo": 50, "finnhub": 50} |
| articles_stored | number | Unique articles stored |
| collisions_detected | number | Duplicates found across sources |
| collision_rate | float | collisions / total_fetched |
| duration_ms | number | Total processing time |

### IngestionBatch

Represents a single ingestion Lambda invocation.

| Field | Type | Description |
|-------|------|-------------|
| batch_id | string | Unique batch identifier |
| started_at | string | ISO8601 start time |
| completed_at | string | ISO8601 end time |
| tickers_processed | list[string] | Tickers in this batch |
| sources_queried | list[string] | Sources queried (tiingo, finnhub) |
| metrics | CollisionMetrics | Aggregated metrics for this batch |
| errors | list[string] | Error messages if any |

## State Transitions

### Article Status

```
           ┌─────────────────────────────┐
           │                             │
           ▼                             │
       ┌───────┐    SNS     ┌──────────┐ │
       │pending│───────────▶│ analyzed │ │
       └───┬───┘            └──────────┘ │
           │                             │
           │ Analysis                    │
           │ failure                     │
           ▼                             │
       ┌───────┐                         │
       │ error │─────────────────────────┘
       └───────┘     Retry (DLQ)
```

### Deduplication States

```
Article arrives from Tiingo
         │
         ▼
    ┌────────────┐
    │ Generate   │
    │ dedup_key  │
    └─────┬──────┘
          │
          ▼
    ┌────────────┐       Yes        ┌────────────┐
    │  Exists?   │─────────────────▶│  Update    │
    └─────┬──────┘                  │  sources[] │
          │ No                      └────────────┘
          ▼
    ┌────────────┐
    │  Create    │
    │  new item  │
    └────────────┘
```

## Validation Rules

### Headline Normalization

1. Convert to lowercase
2. Remove all punctuation (keep alphanumeric and spaces)
3. Collapse multiple whitespace to single space
4. Trim leading/trailing whitespace
5. Result must be non-empty

### Dedup Key

1. Format: `SHA256(normalized_headline | publish_date[:10])[:32]`
2. Must be exactly 32 hexadecimal characters
3. publish_date must be valid ISO8601 date (YYYY-MM-DD)

### Source Attribution

1. article_id: Required, non-empty string
2. url: Required, valid URL format
3. crawl_timestamp: Required, valid ISO8601 timestamp
4. original_headline: Required, non-empty string

### Sources Array

1. Must contain at least one source
2. Valid values: "tiingo", "finnhub"
3. No duplicates allowed
4. Order: chronological by crawl_timestamp

## Indexes

### Primary Table: sentiment-items

| Key Type | Attribute | Pattern |
|----------|-----------|---------|
| Partition Key | source_id | `dedup:{32-char-hex}` |
| Sort Key | timestamp | ISO8601 datetime |

### GSI: by_sentiment

| Key Type | Attribute | Projection |
|----------|-----------|------------|
| Partition Key | sentiment | positive/neutral/negative |
| Sort Key | timestamp | ALL |

### GSI: by_status

| Key Type | Attribute | Projection |
|----------|-----------|------------|
| Partition Key | status | pending/analyzed/error |
| Sort Key | timestamp | KEYS_ONLY |

### GSI: by_tag (existing)

| Key Type | Attribute | Projection |
|----------|-----------|------------|
| Partition Key | tag | Single tag value |
| Sort Key | timestamp | ALL |

## Migration Notes

### Backward Compatibility

- Existing items with `source_id` = `{source}:{article_id}` remain valid
- New items use `source_id` = `dedup:{dedup_key}` format
- Query by old format still works for historical data
- No migration needed - formats coexist

### New Fields

Items created after this feature will include:
- `dedup_key`: 32-char hex string
- `normalized_headline`: Lowercase, punctuation-stripped headline
- `sources`: Array instead of single `source_type`
- `source_attribution`: Map with per-source metadata

### TTL

- All items have `ttl_timestamp` set to created_at + 30 days
- DynamoDB TTL enabled on table (existing)
