# Data Model: Market Data Ingestion

**Branch**: `072-market-data-ingestion` | **Date**: 2025-12-09 | **Phase**: 1

## Entity Relationship

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   DataSource    │──1:N─│    NewsItem     │──1:1─│ SentimentScore  │
│                 │      │                 │      │                 │
│ source_id (PK)  │      │ dedup_key (PK)  │      │ (embedded)      │
│ name            │      │ source          │      │ score           │
│ priority        │      │ headline        │      │ confidence      │
│ availability    │      │ published_at    │      │ label           │
│ last_success    │      │ sentiment       │      └─────────────────┘
│ failure_count   │      │ ...             │
└─────────────────┘      └─────────────────┘
                                │
                                │ 1:N (logged per collection)
                                ▼
                         ┌─────────────────┐
                         │CollectionEvent  │
                         │                 │
                         │ event_id (PK)   │
                         │ source          │
                         │ timestamp       │
                         │ success         │
                         │ item_count      │
                         │ error_message   │
                         └─────────────────┘
```

---

## Entities

### 1. NewsItem

**Purpose**: Stores deduplicated news articles with embedded sentiment.

**Deduplication Key**: SHA256 hash of `{headline}|{source}|{publication_date}`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dedup_key` | String(32) | Yes | Primary key - truncated SHA256 hash |
| `source` | Enum | Yes | "tiingo" or "finnhub" |
| `headline` | String(500) | Yes | Article headline/title |
| `description` | String(5000) | No | Article summary/body |
| `url` | String(2048) | No | Original article URL |
| `published_at` | ISO8601 | Yes | Publication timestamp |
| `ingested_at` | ISO8601 | Yes | When we collected this item |
| `tickers` | List[String] | Yes | Associated stock symbols |
| `tags` | List[String] | No | Article categories/tags |
| `source_name` | String(100) | No | Original publisher (e.g., "reuters") |
| `sentiment` | SentimentScore | No | Embedded sentiment data |
| `entity_type` | String | Yes | "NEWS_ITEM" (for GSI queries) |

**DynamoDB Key Schema**:
- PK: `dedup_key`
- SK: `published_at` (for time-based queries)
- GSI1: PK=`ticker`, SK=`published_at` (for ticker-specific queries)

### 2. SentimentScore (Embedded)

**Purpose**: Sentiment analysis result, embedded in NewsItem.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `score` | Float | Yes | Sentiment value (-1.0 to 1.0) |
| `confidence` | Float | Yes | Confidence level (0.0 to 1.0) |
| `label` | Enum | Yes | "positive", "neutral", or "negative" |
| `model_version` | String | No | Version of sentiment model used |
| `calculated_at` | ISO8601 | No | When sentiment was calculated |

**Label Derivation**:
- `score >= 0.33` → "positive"
- `score <= -0.33` → "negative"
- Otherwise → "neutral"

### 3. CollectionEvent

**Purpose**: Audit log of collection attempts for operational visibility.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_id` | String | Yes | UUID for this event |
| `source` | Enum | Yes | "tiingo" or "finnhub" |
| `timestamp` | ISO8601 | Yes | When collection was attempted |
| `success` | Boolean | Yes | Whether collection succeeded |
| `item_count` | Integer | Yes | Number of items collected (0 if failed) |
| `new_item_count` | Integer | Yes | Items that were not duplicates |
| `duration_ms` | Integer | Yes | Collection duration in milliseconds |
| `error_code` | String | No | Error code if failed |
| `error_message` | String | No | Error details if failed |
| `is_failover` | Boolean | Yes | Whether this was a failover attempt |
| `ttl` | Integer | No | DynamoDB TTL (30 days) |

**DynamoDB Key Schema**:
- PK: `COLLECTION#` (constant for all events)
- SK: `{timestamp}#{source}` (for chronological queries)

### 4. DataSource (Configuration)

**Purpose**: Configuration for each data source with availability tracking.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_id` | Enum | Yes | "tiingo" or "finnhub" |
| `display_name` | String | Yes | Human-readable name |
| `priority` | Integer | Yes | 1=primary, 2=secondary |
| `is_available` | Boolean | Yes | Current availability status |
| `last_success_at` | ISO8601 | No | Last successful collection |
| `last_failure_at` | ISO8601 | No | Last failed collection |
| `consecutive_failures` | Integer | Yes | Failures in current window |
| `failure_window_start` | ISO8601 | No | Start of 15-minute window |

**DynamoDB Key Schema**:
- PK: `SOURCE#{source_id}`
- SK: `CONFIG`

---

## Deduplication Key Generation

```python
import hashlib
from datetime import datetime

def generate_dedup_key(
    headline: str,
    source: str,
    published_at: datetime
) -> str:
    """Generate deduplication key for a news item.

    Uses SHA256 hash of composite key, truncated to 32 chars.
    This provides sufficient uniqueness while being DynamoDB-efficient.

    Args:
        headline: Article headline (case-preserved)
        source: Data source ("tiingo" or "finnhub")
        published_at: Publication timestamp

    Returns:
        32-character hex string
    """
    # Normalize publication date to date-only (ignore time)
    pub_date = published_at.strftime("%Y-%m-%d")

    # Create composite key
    composite = f"{headline}|{source}|{pub_date}"

    # SHA256 hash, truncated to 32 chars
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()[:32]
```

---

## Query Patterns

### Q1: Get recent news for a ticker
```python
response = table.query(
    IndexName="GSI1-ticker-date",
    KeyConditionExpression="ticker = :t AND published_at > :since",
    ExpressionAttributeValues={
        ":t": "AAPL",
        ":since": "2025-12-08T00:00:00Z"
    },
    ScanIndexForward=False,  # Newest first
    Limit=50
)
```

### Q2: Check if news item exists (deduplication)
```python
try:
    table.put_item(
        Item=news_item,
        ConditionExpression="attribute_not_exists(dedup_key)"
    )
    # New item inserted
except ConditionalCheckFailedException:
    # Duplicate - already exists
```

### Q3: Get collection history for monitoring
```python
response = table.query(
    KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
    ExpressionAttributeValues={
        ":pk": "COLLECTION#",
        ":start": "2025-12-09T09:00:00Z",
        ":end": "2025-12-09T16:00:00Z"
    },
    ScanIndexForward=False  # Most recent first
)
```

### Q4: Get data source configuration
```python
response = table.get_item(
    Key={"PK": "SOURCE#tiingo", "SK": "CONFIG"}
)
```

---

## Validation Rules

### NewsItem
- `headline`: Max 500 chars, required, non-empty
- `description`: Max 5000 chars, optional
- `url`: Valid URL format if provided
- `published_at`: Must be within last 7 days
- `tickers`: 1-10 items, each uppercase 1-5 chars
- `sentiment.score`: Range -1.0 to 1.0
- `sentiment.confidence`: Range 0.0 to 1.0

### CollectionEvent
- `item_count`: Non-negative integer
- `duration_ms`: Non-negative integer, max 60000 (1 minute timeout)
- `error_message`: Max 1000 chars

---

## DynamoDB Table Design

### Single-Table Design

```
Table: sentiment-analyzer-{env}
├── NewsItem: PK=dedup_key, SK=published_at
├── CollectionEvent: PK=COLLECTION#, SK={timestamp}#{source}
├── DataSource: PK=SOURCE#{id}, SK=CONFIG
└── (existing entities remain unchanged)
```

### GSI1 (ticker-date-index)
- PK: `ticker`
- SK: `published_at`
- Projection: ALL
- Use: Get news for specific ticker sorted by date

### Capacity
- On-demand billing (per constitution)
- Expected: 10,000 items/day = ~300 WCU sustained during market hours
- Read-heavy pattern: cache at application layer
