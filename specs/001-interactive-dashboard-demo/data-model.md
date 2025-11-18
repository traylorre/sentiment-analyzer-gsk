# Data Model: Interactive Dashboard Demo

**Feature**: `001-interactive-dashboard-demo` | **Date**: 2025-11-17
**Architecture**: Regional Multi-AZ (single table design)

## Purpose

Define the DynamoDB schema, access patterns, and data validation rules for the sentiment analysis demo with production-grade reliability and compliance.

## Architecture Overview

This implementation uses a **Regional Multi-AZ single table design**:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SINGLE TABLE ARCHITECTURE                     │
│                                                                   │
│  Ingestion Lambda ──────┐                                        │
│  Analysis Lambda   ──────┼──► DynamoDB: sentiment-items          │
│  Dashboard Lambda  ──────┘    (us-east-1)                        │
│                               • Multi-AZ replication (automatic) │
│                               • Point-in-time recovery (35 days) │
│                               • 3 GSIs for efficient queries     │
│                               • TTL auto-cleanup (30 days)       │
│                                                                   │
│  ✅ Write path: Ingestion/Analysis → Primary table               │
│  ✅ Read path: Dashboard → GSIs (by_sentiment, by_tag, by_status)│
│  ✅ Redundancy: Multi-AZ (AWS-managed, synchronous)              │
│  ✅ Backup: Point-in-time recovery + daily backups               │
└─────────────────────────────────────────────────────────────────┘
```

**Key Design Principles**:
- ✅ Single source of truth (one table)
- ✅ GSIs for efficient dashboard queries
- ✅ No stream processor (simplified architecture)
- ✅ Regional data residency (GDPR/compliance)
- ✅ Cost-optimized (on-demand pricing)

---

## Table: `sentiment-items`

**Purpose**: Single source of truth for all sentiment analysis data

**Partition Key (PK)**: `source_id` (String)
- Format: `{source_type}#{stable_id}`
- Examples:
  - `newsapi#abc123def456` (SHA-256 hash of article URL)
  - `twitter#tweet-456789` (future)
- Purpose: Unique identifier for deduplication

**Sort Key (SK)**: `timestamp` (String)
- Format: ISO8601 timestamp (`2025-11-17T14:30:00.000Z`)
- Purpose: Time-ordered retrieval, enables "recent items" queries

**Capacity Mode**: On-demand (no provisioned capacity management)

**Redundancy**:
- Multi-AZ replication: Automatic (synchronous, AWS-managed)
- Point-in-time recovery (PITR): Enabled (35-day retention)
- On-demand backups: Daily at 02:00 UTC (7-day retention)

**TTL**: 30 days (attribute: `ttl_timestamp`)

---

## Attributes

| Attribute | Type | Required | Description | Validation |
|---|---|---|---|---|
| `source_id` | String | Yes | PK - Unique identifier | Max 256 chars, pattern: `^[a-z]+#[a-zA-Z0-9]+$` |
| `timestamp` | String | Yes | SK - ISO8601 timestamp | Valid ISO8601, UTC timezone |
| `source_type` | String | Yes | Source adapter type | Enum: `newsapi`, `twitter`, `reddit` |
| `source_url` | String | No | Original item URL | Valid HTTPS URL or omit |
| `text_snippet` | String | No | First 200 chars of content | Max 200 chars, no control chars |
| `sentiment` | String | Conditional | Classification result | Enum: `positive`, `neutral`, `negative` |
| `score` | Number | Conditional | Confidence score (0.0-1.0) | Float 0.0-1.0 (DynamoDB Number type) |
| `model_version` | String | Yes | Model identifier | Pattern: `^v\d+\.\d+\.\d+$` (e.g., `v1.0.0`) |
| `matched_tags` | StringSet | Yes | Watch tags that matched | Min 1, max 5 items, each max 50 chars |
| `metadata` | Map | No | Source-specific fields | See Metadata Schema below |
| `status` | String | Yes | Processing state | Enum: `pending`, `analyzed` |
| `ttl_timestamp` | Number | Yes | TTL expiry (Unix epoch) | Epoch seconds, 30 days from ingestion |

**Conditional Fields**:
- `sentiment` and `score` are required when `status = "analyzed"`, absent when `status = "pending"`

---

## Metadata Schema (Optional)

Source-specific fields stored as a Map:

### NewsAPI Metadata

```json
{
  "title": "Article headline",
  "author": "Author name or 'Unknown'",
  "published_at": "2025-11-17T10:00:00Z",
  "source_name": "BBC News"
}
```

### Twitter Metadata (Future)

```json
{
  "username": "@example",
  "retweet_count": 42,
  "like_count": 128,
  "created_at": "2025-11-17T10:00:00Z"
}
```

---

## Global Secondary Indexes (GSIs)

### GSI 1: `by_sentiment`

**Purpose**: Query items by sentiment classification (e.g., "show all negative sentiment")

**Partition Key**: `sentiment` (String)
**Sort Key**: `timestamp` (String)

**Projection**: `ALL` (all attributes)

**Access Pattern**:
```python
response = table.query(
    IndexName='by_sentiment',
    KeyConditionExpression=Key('sentiment').eq('negative') & Key('timestamp').gt('2025-11-16T00:00:00Z'),
    ScanIndexForward=False,  # Most recent first
    Limit=20
)
```

---

### GSI 2: `by_tag`

**Purpose**: Query items by watch tag (e.g., "show all items tagged 'AI'")

**Partition Key**: `tag` (String) - **Derived attribute** (see below)
**Sort Key**: `timestamp` (String)

**Projection**: `ALL` (all attributes)

**Derived Attribute Strategy**:
Since `matched_tags` is a StringSet, we cannot use it directly as a GSI key. Instead:
1. **Write multiple items** to the GSI (one per tag)
2. **Use DynamoDB Streams** to automatically fan-out (if needed)
3. **OR: Write fan-out in application code** (simpler for Demo 1)

**Fan-out Strategy** (Application Code):
```python
# In ingestion Lambda, write one item per tag
matched_tags = ['AI', 'technology']
for tag in matched_tags:
    table.put_item(
        Item={
            'source_id': 'newsapi#abc123',
            'timestamp': '2025-11-17T14:30:00Z',
            'tag': tag,  # Derived attribute for GSI
            'sentiment': 'positive',
            'score': 0.87,
            # ... other attributes
        },
        ConditionExpression='attribute_not_exists(source_id)'
    )
```

**Access Pattern**:
```python
response = table.query(
    IndexName='by_tag',
    KeyConditionExpression=Key('tag').eq('AI'),
    ScanIndexForward=False,
    Limit=20
)
```

---

### GSI 3: `by_status`

**Purpose**: Monitor pending items (for operational dashboards)

**Partition Key**: `status` (String)
**Sort Key**: `timestamp` (String)

**Projection**: `KEYS_ONLY` (minimal storage)

**Access Pattern**:
```python
# Find all pending items older than 5 minutes (stuck items)
response = table.query(
    IndexName='by_status',
    KeyConditionExpression=Key('status').eq('pending') & Key('timestamp').lt(five_minutes_ago),
    Limit=100
)
```

**Use Cases**:
- CloudWatch alarm on pending items > 5 minutes old (analysis Lambda down)
- Operational dashboard showing ingestion lag

---

## Access Patterns

### Pattern 1: Deduplication Check (Ingestion Lambda)

**Query**: Check if `source_id` already exists

```python
try:
    table.put_item(
        Item={
            'source_id': 'newsapi#abc123',
            'timestamp': '2025-11-17T14:30:00Z',
            'status': 'pending',
            # ... other fields
        },
        ConditionExpression='attribute_not_exists(source_id)'
    )
    # Success: New item inserted
except ClientError as e:
    if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
        # Duplicate, skip
        pass
```

**Cost**: 1 WCU per attempt (charged even if condition fails)

---

### Pattern 2: Update Sentiment (Analysis Lambda)

**Query**: Update item with sentiment result

```python
table.update_item(
    Key={
        'source_id': 'newsapi#abc123',
        'timestamp': '2025-11-17T14:30:00Z'
    },
    UpdateExpression='SET #status = :analyzed, sentiment = :sentiment, score = :score',
    ConditionExpression='attribute_not_exists(sentiment)',  # Prevent overwrite
    ExpressionAttributeNames={
        '#status': 'status'  # 'status' is a reserved word
    },
    ExpressionAttributeValues={
        ':analyzed': 'analyzed',
        ':sentiment': 'positive',
        ':score': Decimal('0.87')
    }
)
```

**Cost**: 1 WCU (if item < 1KB)

---

### Pattern 3: Dashboard Query by Sentiment (Dashboard Lambda)

**Query**: Get last 20 items with negative sentiment

```python
from boto3.dynamodb.conditions import Key

response = table.query(
    IndexName='by_sentiment',
    KeyConditionExpression=Key('sentiment').eq('negative'),
    ScanIndexForward=False,  # Descending order (most recent first)
    Limit=20
)

items = response['Items']
```

**Cost**: ~0.5 RCU (eventually consistent reads)

---

### Pattern 4: Dashboard Query by Tag (Dashboard Lambda)

**Query**: Get last 20 items tagged 'AI'

```python
response = table.query(
    IndexName='by_tag',
    KeyConditionExpression=Key('tag').eq('AI'),
    ScanIndexForward=False,
    Limit=20
)
```

**Cost**: ~0.5 RCU (eventually consistent reads)

---

### Pattern 5: Monitor Stuck Items (Metrics Lambda)

**Query**: Find pending items older than 5 minutes

```python
from datetime import datetime, timedelta

five_minutes_ago = (datetime.utcnow() - timedelta(minutes=5)).isoformat() + 'Z'

response = table.query(
    IndexName='by_status',
    KeyConditionExpression=Key('status').eq('pending') & Key('timestamp').lt(five_minutes_ago),
    ProjectionExpression='source_id, timestamp',
    Limit=100
)

stuck_count = len(response['Items'])
# Emit CloudWatch metric
cloudwatch.put_metric_data(
    Namespace='SentimentAnalyzer',
    MetricData=[{
        'MetricName': 'StuckItems',
        'Value': stuck_count,
        'Unit': 'Count'
    }]
)
```

**Cost**: ~0.25 RCU (KEYS_ONLY projection)

---

## Data Validation

### Pydantic Schemas

**Ingestion Lambda**:
```python
from pydantic import BaseModel, Field, HttpUrl, validator
from datetime import datetime
from typing import Optional, List

class NewsArticle(BaseModel):
    """External API response validation"""
    title: str = Field(..., max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    url: HttpUrl
    publishedAt: datetime
    author: Optional[str] = Field('Unknown', max_length=200)
    source: dict

class SentimentItem(BaseModel):
    """DynamoDB item validation"""
    source_id: str = Field(..., regex=r'^[a-z]+#[a-zA-Z0-9]+$', max_length=256)
    timestamp: str = Field(..., regex=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$')
    source_type: str = Field(..., regex=r'^(newsapi|twitter|reddit)$')
    source_url: Optional[HttpUrl]
    text_snippet: Optional[str] = Field(None, max_length=200)
    sentiment: Optional[str] = Field(None, regex=r'^(positive|neutral|negative)$')
    score: Optional[float] = Field(None, ge=0.0, le=1.0)
    model_version: str = Field(..., regex=r'^v\d+\.\d+\.\d+$')
    matched_tags: List[str] = Field(..., min_items=1, max_items=5)
    status: str = Field(..., regex=r'^(pending|analyzed)$')
    ttl_timestamp: int

    @validator('matched_tags')
    def validate_tags(cls, tags):
        for tag in tags:
            if len(tag) > 50:
                raise ValueError(f'Tag too long: {tag}')
            if not tag.replace('-', '').replace('_', '').isalnum():
                raise ValueError(f'Invalid tag characters: {tag}')
        return tags
```

**Analysis Lambda**:
```python
class AnalysisResult(BaseModel):
    """Sentiment analysis result validation"""
    sentiment: str = Field(..., regex=r'^(positive|neutral|negative)$')
    score: float = Field(..., ge=0.0, le=1.0)

    @validator('score')
    def round_score(cls, v):
        return round(v, 4)  # Precision: 4 decimal places
```

---

## Cost Estimates

### Demo Scale (100 items/hour, 30-day TTL)

**Writes**:
- Ingestion: 100 items/hour × 24h × 30 days = 72,000 writes/month
- Analysis updates: 72,000 updates/month
- **Total WCUs**: 144,000/month = **$0.72** (on-demand: $1.25 per million writes)

**Reads**:
- Dashboard queries: 2 queries/sec × 60s × 60m × 24h × 30d = 5.2M reads/month
- Each query returns 20 items (4KB avg) = 20KB per query
- RCUs: 5.2M queries × 20KB / 4KB = 26M RCUs eventually consistent
- **Total cost**: 26M / 2 (eventually consistent) = 13M RCUs = **$0.25** (on-demand: $0.25 per million)

**Storage**:
- Average item size: 1KB
- Items stored: 72,000 (30-day TTL)
- **Total storage**: 72MB = **$0.02** ($0.25 per GB-month)

**GSI costs**:
- 3 GSIs × storage = 3 × $0.02 = **$0.06**

**Total DynamoDB**: **$1.05/month**

---

### Production Scale (10,000 items/hour)

**Writes**: 7.2M writes/month = **$9.00**
**Reads**: 26M RCUs (same query rate, different data volume) = **$3.25**
**Storage**: ~7GB = **$1.75**
**GSI storage**: 3 × $1.75 = **$5.25**

**Total DynamoDB**: **$19.25/month** (very cost-effective)

---

## Migration Strategy (If Needed)

If we need to change schema later:

1. **Add new GSI**: Online operation, no downtime
2. **Remove GSI**: Online operation, no downtime
3. **Add new attribute**: Write new code, backfill via scan + update
4. **Rename attribute**: Use `ExpressionAttributeNames` (no migration needed)

---

## Backup & Recovery

**Automatic Backups** (Point-in-time recovery):
- Retention: 35 days
- Granularity: 5-minute intervals
- Restore RTO: < 4 hours

**On-Demand Backups** (Daily):
- Schedule: 02:00 UTC daily
- Retention: 7 days
- Use case: Rollback to known-good state

**Cross-Region Backup**:
- S3 bucket replication: us-east-1 → us-west-2
- Export to S3: Weekly full export (use DynamoDB export feature)
- Retention: 90 days

---

## Security

**Encryption**:
- At rest: AWS-managed keys (default, no extra cost)
- In transit: TLS 1.2+ (enforced by boto3)

**IAM Policies**:
- Ingestion Lambda: `dynamodb:PutItem` only
- Analysis Lambda: `dynamodb:UpdateItem`, `dynamodb:GetItem` only
- Dashboard Lambda: `dynamodb:Query`, `dynamodb:GetItem` (read-only)
- Metrics Lambda: `dynamodb:Query` on `by_status` GSI only

**TTL Security**:
- Automatic deletion after 30 days (reduces attack surface)
- No manual cleanup required (prevents accidental mass deletion)

---

## Monitoring

**CloudWatch Alarms**:
1. `UserErrors > 10` in 5 minutes (validation failures)
2. `SystemErrors > 5` in 5 minutes (DynamoDB throttling)
3. `ConsumedWriteCapacityUnits > 1000` in 1 minute (unexpected traffic spike)
4. `StuckItems > 10` (pending items older than 5 minutes)

**CloudWatch Insights Queries**:
```
# Find most common tags
fields @timestamp, matched_tags
| stats count() by matched_tags

# Find slow queries
fields @timestamp, @duration
| filter @duration > 1000
| sort @duration desc
```

---

## Testing Strategy

**Unit Tests**:
- Pydantic schema validation
- Hash generation (deduplication)
- TTL calculation

**Integration Tests**:
- Write → Read consistency (verify Multi-AZ replication)
- GSI query accuracy
- Conditional write failures (deduplication)
- TTL deletion (wait 30 days in staging environment)

**Load Tests**:
- Burst write: 1000 items in 10 seconds (test on-demand scaling)
- Sustained read: 100 queries/sec for 10 minutes (test GSI performance)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
