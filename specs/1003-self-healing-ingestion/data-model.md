# Data Model: Self-Healing Ingestion

**Feature**: 1003-self-healing-ingestion
**Date**: 2025-12-20

## Entities

### SentimentItem (Existing)

The primary entity stored in `{environment}-sentiment-items` DynamoDB table.

| Attribute | Type | Description | Required |
|-----------|------|-------------|----------|
| `source_id` | String (PK) | Unique identifier: `{source}:{article_id}` | Yes |
| `timestamp` | String (ISO 8601) | Article published timestamp | Yes |
| `status` | String | Processing status: `pending` or `analyzed` | Yes |
| `sentiment` | String | Sentiment classification: `positive`, `neutral`, `negative` | After analysis |
| `source_type` | String | Data source: `tiingo` or `finnhub` | Yes |
| `text_for_analysis` | String | Combined title + description for analysis | Yes |
| `matched_tickers` | List[String] | Stock symbols mentioned in article | Yes |
| `ttl_timestamp` | Number | Unix timestamp for auto-deletion (30 days) | Yes |
| `metadata` | Map | Additional article metadata | Optional |

**State Transitions**:
```
[Ingestion Lambda]     [Analysis Lambda]
     |                      |
     v                      v
  pending  ─────────────> analyzed
     ^
     |
[Self-Healing]
(republish to SNS)
```

### Global Secondary Indexes

#### by_status (Existing)

Used for self-healing queries.

| Key | Attribute | Notes |
|-----|-----------|-------|
| Hash Key | `status` | "pending" or "analyzed" |
| Range Key | `timestamp` | ISO 8601 string (sortable) |
| Projection | KEYS_ONLY | Only `source_id`, `status`, `timestamp` |

**Query Pattern** (Self-Healing):
```python
# Get pending items older than 1 hour
response = table.query(
    IndexName="by_status",
    KeyConditionExpression="status = :status AND #ts < :threshold",
    ExpressionAttributeNames={"#ts": "timestamp"},
    ExpressionAttributeValues={
        ":status": "pending",
        ":threshold": threshold_iso,  # 1 hour ago
    },
    Limit=100,  # Batch limit per self-healing run
)
```

#### by_sentiment (Existing)

Used by SSE Lambda for dashboard queries.

| Key | Attribute | Notes |
|-----|-----------|-------|
| Hash Key | `sentiment` | "positive", "neutral", "negative" |
| Range Key | `timestamp` | ISO 8601 string |
| Projection | ALL | Full item data |

## Message Formats

### Analysis Request (SNS)

Message published to `{environment}-sentiment-analysis-requests` topic.

```json
{
  "source_id": "finnhub:137825212",
  "source_type": "finnhub",
  "text_for_analysis": "Company XYZ reports record earnings...",
  "model_version": "v1.0.0",
  "matched_tickers": ["XYZ"],
  "timestamp": "2025-12-19T20:14:12Z"
}
```

**MessageAttributes**:
```json
{
  "source_type": {
    "DataType": "String",
    "StringValue": "finnhub"
  }
}
```

### Self-Healing Log Entry

Structured log format for observability.

```json
{
  "level": "INFO",
  "message": "Self-healing completed",
  "extra": {
    "stale_items_found": 5,
    "items_republished": 5,
    "threshold_hours": 1,
    "execution_time_ms": 1234.56
  }
}
```

## Validation Rules

### Stale Item Detection

An item is considered **stale** and eligible for self-healing if ALL conditions are true:

1. `status == "pending"` (not yet analyzed)
2. `timestamp < (now - 1 hour)` (older than threshold)
3. `sentiment` attribute does not exist (never analyzed)

### Republishing Rules

1. Maximum 100 items per self-healing run (FR-004)
2. Items are republished in timestamp order (oldest first)
3. SNS publish uses batch API (max 10 per call)
4. Partial failures logged but do not abort remaining items (FR-008)

## Access Patterns Summary

| Pattern | GSI | Query | Notes |
|---------|-----|-------|-------|
| Get stale pending items | by_status | `status = "pending" AND timestamp < threshold` | Self-healing |
| Get items by sentiment | by_sentiment | `sentiment = "positive"` | Dashboard SSE |
| Get item by source_id | (base table) | `source_id = "finnhub:123"` | After GSI query |

## CloudWatch Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `SelfHealingItemsFound` | Count | Stale items detected |
| `SelfHealingItemsRepublished` | Count | Items successfully republished |
| `SelfHealingExecutionTime` | Milliseconds | Self-healing check duration |
