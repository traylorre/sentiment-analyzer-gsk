# Data Model: Interactive Dashboard Demo

**Feature**: `001-interactive-dashboard-demo` | **Date**: 2025-11-16

## Purpose

Define the DynamoDB schema, access patterns, and data validation rules for the sentiment analysis demo.

---

## Entity: SentimentItem

Represents a single analyzed item (news article, tweet, etc.) with sentiment results.

### Primary Table: `sentiment_items`

**Partition Key (PK)**: `source_id` (String)
- Format: `{source_type}#{stable_id}`
- Examples:
  - `newsapi#article-abc123`
  - `twitter#tweet-456789`
- Purpose: Unique identifier for deduplication

**Sort Key (SK)**: `ingested_at` (String)
- Format: ISO8601 timestamp (`2025-11-16T14:30:00.000Z`)
- Purpose: Time-ordered retrieval, enables "recent items" queries

### Attributes

| Attribute | Type | Required | Description | Validation |
|---|---|---|---|---|
| `source_id` | String | Yes | PK (see above) | Max 256 chars, pattern: `^[a-z]+#[a-zA-Z0-9_-]+$` |
| `ingested_at` | String | Yes | SK (ISO8601) | Valid ISO8601 timestamp |
| `source_type` | String | Yes | Source adapter type | Enum: `newsapi`, `twitter`, `reddit` |
| `source_url` | String | No | Original item URL | Valid HTTPS URL or omit |
| `text_snippet` | String | No | First 200 chars | Max 200 chars, no control chars |
| `sentiment` | String | Yes | Classification result | Enum: `positive`, `neutral`, `negative` |
| `score` | Number | Yes | Confidence score | Float 0.0-1.0 (DynamoDB Number type) |
| `model_version` | String | Yes | Model identifier | Pattern: `^v\\d+\\.\\d+\\.\\d+$` (e.g., `v1.0.0`) |
| `matched_tags` | StringSet | Yes | Watch tags that matched | Max 5 items, each max 50 chars |
| `metadata` | Map | No | Source-specific fields | See Metadata Schema below |

### Metadata Schema (Optional)

Source-specific fields stored as a Map:

**NewsAPI metadata**:
```json
{
  "author": "John Doe",
  "title": "Article title",
  "published_at": "2025-11-16T10:00:00Z",
  "source_name": "BBC News"
}
```

**Twitter metadata** (future):
```json
{
  "username": "elonmusk",
  "retweet_count": 150,
  "like_count": 500
}
```

---

## Global Secondary Index (GSI): `by_timestamp`

**Purpose**: Query recent items across all sources for dashboard display

**Partition Key**: `source_type` (String)
**Sort Key**: `ingested_at` (String)

**Projection**: ALL (include all attributes)

### Access Pattern

```python
# Query last 20 items for newsapi
response = dynamodb.query(
    TableName='sentiment_items',
    IndexName='by_timestamp',
    KeyConditionExpression='source_type = :st',
    ExpressionAttributeValues={':st': {'S': 'newsapi'}},
    ScanIndexForward=False,  # Descending (newest first)
    Limit=20
)
```

---

## Global Secondary Index (GSI): `by_model_version`

**Purpose**: Query items analyzed by specific model version (for A/B testing, model eval)

**Partition Key**: `model_version` (String)
**Sort Key**: `ingested_at` (String)

**Projection**: ALL

### Access Pattern

```python
# Get all items analyzed by v1.2.0 in last 24 hours
response = dynamodb.query(
    TableName='sentiment_items',
    IndexName='by_model_version',
    KeyConditionExpression='model_version = :mv AND ingested_at > :ts',
    ExpressionAttributeValues={
        ':mv': {'S': 'v1.2.0'},
        ':ts': {'S': '2025-11-15T14:00:00.000Z'}
    },
    ScanIndexForward=False
)
```

---

## Access Patterns

### 1. Insert New Item (Deduplication)

Use conditional write to prevent duplicate inserts:

```python
import boto3
from datetime import datetime

dynamodb = boto3.client('dynamodb')

def insert_item_if_new(item_data):
    """
    Insert item only if source_id doesn't exist (deduplication).
    Raises ConditionalCheckFailedException if duplicate.
    """
    try:
        response = dynamodb.put_item(
            TableName='sentiment_items',
            Item={
                'source_id': {'S': item_data['source_id']},
                'ingested_at': {'S': datetime.utcnow().isoformat() + 'Z'},
                'source_type': {'S': item_data['source_type']},
                'sentiment': {'S': item_data['sentiment']},
                'score': {'N': str(item_data['score'])},
                'model_version': {'S': item_data['model_version']},
                'matched_tags': {'SS': item_data['matched_tags']},
                # ... other attributes
            },
            ConditionExpression='attribute_not_exists(source_id)'  # Dedup check
        )
        return True
    except dynamodb.exceptions.ConditionalCheckFailedException:
        # Item already exists, skip
        return False
```

### 2. Query Recent Items (Dashboard)

```python
def get_recent_items(source_type='newsapi', limit=20):
    """
    Fetch last N items for dashboard display.
    Uses by_timestamp GSI for efficient time-ordered retrieval.
    """
    response = dynamodb.query(
        TableName='sentiment_items',
        IndexName='by_timestamp',
        KeyConditionExpression='source_type = :st',
        ExpressionAttributeValues={':st': {'S': source_type}},
        ScanIndexForward=False,  # Newest first
        Limit=limit
    )

    items = []
    for item in response['Items']:
        items.append({
            'source_id': item['source_id']['S'],
            'ingested_at': item['ingested_at']['S'],
            'sentiment': item['sentiment']['S'],
            'score': float(item['score']['N']),
            'text_snippet': item.get('text_snippet', {}).get('S', ''),
            'matched_tags': list(item['matched_tags']['SS']),
        })

    return items
```

### 3. Aggregate Sentiment Distribution (Metrics)

```python
def get_sentiment_distribution(source_type='newsapi', hours=24):
    """
    Calculate sentiment distribution for dashboard pie chart.
    Queries recent items and aggregates client-side.
    """
    from datetime import datetime, timedelta

    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + 'Z'

    response = dynamodb.query(
        TableName='sentiment_items',
        IndexName='by_timestamp',
        KeyConditionExpression='source_type = :st AND ingested_at > :cutoff',
        ExpressionAttributeValues={
            ':st': {'S': source_type},
            ':cutoff': {'S': cutoff}
        },
        ProjectionExpression='sentiment'  # Only fetch needed attribute
    )

    distribution = {'positive': 0, 'neutral': 0, 'negative': 0}
    for item in response['Items']:
        sentiment = item['sentiment']['S']
        distribution[sentiment] += 1

    return distribution
```

### 4. Tag Match Counts (Bar Chart)

```python
def get_tag_match_counts(source_type='newsapi', hours=24):
    """
    Count items matching each tag for bar chart.
    """
    from datetime import datetime, timedelta
    from collections import Counter

    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + 'Z'

    response = dynamodb.query(
        TableName='sentiment_items',
        IndexName='by_timestamp',
        KeyConditionExpression='source_type = :st AND ingested_at > :cutoff',
        ExpressionAttributeValues={
            ':st': {'S': source_type},
            ':cutoff': {'S': cutoff}
        },
        ProjectionExpression='matched_tags'
    )

    tag_counter = Counter()
    for item in response['Items']:
        tags = list(item['matched_tags']['SS'])
        tag_counter.update(tags)

    return dict(tag_counter)
```

---

## State Transitions

### Item Lifecycle

```
1. [External API] → fetch item → check dedup hash
                                      ↓
2. [Ingestion Lambda] → insert with status=pending
                                      ↓
3. [Analysis Lambda] → update with sentiment/score
                                      ↓
4. [Dashboard] → query recent items → display
```

**Note**: For demo simplicity, we insert items with sentiment already computed (single-pass). Future enhancement: two-pass with status field (`pending` → `analyzed`).

---

## Validation Rules

### Source ID Validation

```python
import re

def validate_source_id(source_id: str) -> bool:
    """
    Validate source_id format: {source_type}#{stable_id}
    """
    pattern = r'^[a-z]+#[a-zA-Z0-9_-]+$'
    if not re.match(pattern, source_id):
        raise ValueError(f"Invalid source_id format: {source_id}")

    if len(source_id) > 256:
        raise ValueError(f"source_id exceeds 256 chars: {source_id}")

    return True
```

### Timestamp Validation

```python
from datetime import datetime

def validate_timestamp(timestamp: str) -> bool:
    """
    Validate ISO8601 timestamp format.
    """
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return True
    except ValueError as e:
        raise ValueError(f"Invalid ISO8601 timestamp: {timestamp}") from e
```

### Sentiment Validation

```python
VALID_SENTIMENTS = {'positive', 'neutral', 'negative'}

def validate_sentiment(sentiment: str) -> bool:
    """
    Validate sentiment enum.
    """
    if sentiment not in VALID_SENTIMENTS:
        raise ValueError(f"Invalid sentiment: {sentiment}. Must be one of {VALID_SENTIMENTS}")

    return True
```

### Score Validation

```python
def validate_score(score: float) -> bool:
    """
    Validate confidence score range.
    """
    if not (0.0 <= score <= 1.0):
        raise ValueError(f"Score must be 0.0-1.0, got: {score}")

    return True
```

### Matched Tags Validation

```python
def validate_matched_tags(tags: list[str]) -> bool:
    """
    Validate matched tags (max 5, each max 50 chars).
    """
    if len(tags) > 5:
        raise ValueError(f"Too many matched tags (max 5): {len(tags)}")

    for tag in tags:
        if len(tag) > 50:
            raise ValueError(f"Tag exceeds 50 chars: {tag}")

        if not tag.strip():
            raise ValueError("Empty tag not allowed")

    return True
```

---

## DynamoDB Table Configuration (Terraform)

```hcl
resource "aws_dynamodb_table" "sentiment_items" {
  name           = "sentiment-items"
  billing_mode   = "PAY_PER_REQUEST"  # On-demand for demo
  hash_key       = "source_id"
  range_key      = "ingested_at"

  attribute {
    name = "source_id"
    type = "S"
  }

  attribute {
    name = "ingested_at"
    type = "S"
  }

  attribute {
    name = "source_type"
    type = "S"
  }

  attribute {
    name = "model_version"
    type = "S"
  }

  # GSI: by_timestamp
  global_secondary_index {
    name            = "by_timestamp"
    hash_key        = "source_type"
    range_key       = "ingested_at"
    projection_type = "ALL"
  }

  # GSI: by_model_version
  global_secondary_index {
    name            = "by_model_version"
    hash_key        = "model_version"
    range_key       = "ingested_at"
    projection_type = "ALL"
  }

  # Server-side encryption
  server_side_encryption {
    enabled = true
  }

  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  # TTL for automatic cleanup (optional, for cost control)
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Environment = "demo"
    Feature     = "001-interactive-dashboard-demo"
  }
}
```

---

## Data Retention & Cleanup

### TTL Configuration (Optional)

To auto-delete items after 30 days:

```python
from datetime import datetime, timedelta

def set_item_ttl(item: dict) -> dict:
    """
    Add TTL attribute for auto-cleanup after 30 days.
    DynamoDB will delete items when expires_at < current_time.
    """
    expires_at = datetime.utcnow() + timedelta(days=30)
    item['expires_at'] = {'N': str(int(expires_at.timestamp()))}
    return item
```

Enable in Terraform:
```hcl
ttl {
  attribute_name = "expires_at"
  enabled        = true
}
```

---

## Sample Item

```json
{
  "source_id": {
    "S": "newsapi#bbc-news-ai-regulation-2025-11-16"
  },
  "ingested_at": {
    "S": "2025-11-16T14:30:15.000Z"
  },
  "source_type": {
    "S": "newsapi"
  },
  "source_url": {
    "S": "https://www.bbc.com/news/technology-12345678"
  },
  "text_snippet": {
    "S": "European Union announces sweeping AI regulation framework targeting tech giants. The new rules will require transparency in algorithmic decision-making and impose hefty fines for violations..."
  },
  "sentiment": {
    "S": "neutral"
  },
  "score": {
    "N": "0.72"
  },
  "model_version": {
    "S": "v1.0.0"
  },
  "matched_tags": {
    "SS": ["AI", "regulation", "europe"]
  },
  "metadata": {
    "M": {
      "author": {
        "S": "Jane Smith"
      },
      "title": {
        "S": "EU Announces AI Regulation Framework"
      },
      "published_at": {
        "S": "2025-11-16T10:00:00Z"
      },
      "source_name": {
        "S": "BBC News"
      }
    }
  }
}
```

---

## Performance Considerations

### Read/Write Capacity Planning (Demo Scale)

**Expected Load**:
- Ingestion: 5 tags × 100 items/hour = ~500 writes/hour = 0.14 writes/second
- Dashboard queries: 10 concurrent users × 1 query/5s = 2 reads/second
- Aggregation queries: 3 metrics × 1 query/10s = 0.3 scans/second

**On-Demand Pricing** (demo scale):
- Writes: 500/hour × 720 hours/month = 360,000 writes/month
- Reads: 2 reads/s × 2.6M seconds/month = 5.2M reads/month
- Cost: $0.25/1M writes + $0.05/1M reads = $0.09 + $0.26 = **$0.35/month**

**Verdict**: On-demand mode is cost-effective for demo (scales to zero when idle)

### Query Optimization

1. **Use Projection Expressions**: Fetch only needed attributes to reduce data transfer
2. **Limit Results**: Always set `Limit` parameter for dashboard queries
3. **Client-Side Aggregation**: Aggregate sentiment distribution in Lambda (not DynamoDB Scan)
4. **GSI Coverage**: Ensure all access patterns use GSI (avoid table scans)

---

## Security & Compliance

### Attribute-Level Encryption (Future)

For production, encrypt `text_snippet` and `metadata` fields:

```python
from cryptography.fernet import Fernet

def encrypt_sensitive_fields(item: dict, key: bytes) -> dict:
    """
    Encrypt text_snippet and metadata before storage.
    """
    cipher = Fernet(key)

    if 'text_snippet' in item:
        item['text_snippet'] = cipher.encrypt(item['text_snippet'].encode()).decode()

    # ... encrypt metadata fields

    return item
```

### IAM Least-Privilege

Lambda execution roles should have minimal permissions:

```hcl
resource "aws_iam_policy" "lambda_dynamodb_write" {
  name = "lambda-sentiment-items-write"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.sentiment_items.arn
        Condition = {
          StringEquals = {
            "dynamodb:LeadingKeys" = ["newsapi#*"]
          }
        }
      }
    ]
  })
}
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_data_model.py
import pytest
from datetime import datetime

def test_validate_source_id():
    assert validate_source_id("newsapi#article-123") == True

    with pytest.raises(ValueError):
        validate_source_id("invalid format")  # No '#'

    with pytest.raises(ValueError):
        validate_source_id("newsapi#" + "x" * 300)  # Too long

def test_validate_score():
    assert validate_score(0.5) == True
    assert validate_score(0.0) == True
    assert validate_score(1.0) == True

    with pytest.raises(ValueError):
        validate_score(-0.1)  # Below range

    with pytest.raises(ValueError):
        validate_score(1.5)  # Above range
```

### Integration Tests

```python
# tests/integration/test_dynamodb.py
import boto3
from moto import mock_dynamodb

@mock_dynamodb
def test_insert_and_query_item():
    # Setup mock DynamoDB
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    dynamodb.create_table(...)  # Create sentiment_items table

    # Insert test item
    result = insert_item_if_new({
        'source_id': 'newsapi#test-123',
        'source_type': 'newsapi',
        'sentiment': 'positive',
        'score': 0.85,
        'model_version': 'v1.0.0',
        'matched_tags': ['test', 'demo']
    })

    assert result == True

    # Verify deduplication
    result = insert_item_if_new({
        'source_id': 'newsapi#test-123',  # Duplicate
        ...
    })

    assert result == False  # Should skip duplicate

    # Query recent items
    items = get_recent_items(source_type='newsapi', limit=10)
    assert len(items) == 1
    assert items[0]['source_id'] == 'newsapi#test-123'
```

---

## Migration Path (Future)

For production scale (beyond demo):

1. **Switch to Provisioned Capacity**: More cost-effective at >1M requests/month
2. **Add Caching Layer**: DynamoDB DAX for hot data (dashboard metrics)
3. **Time-Series Optimization**: Consider TimeStream for metrics aggregation
4. **Archive Old Data**: S3 + Athena for historical analysis (items >90 days)

---

## Summary

**Table**: `sentiment_items`
- PK: `source_id` (deduplication key)
- SK: `ingested_at` (time-ordered retrieval)
- GSIs: `by_timestamp` (dashboard queries), `by_model_version` (model eval)

**Access Patterns**:
1. Insert with dedup (conditional write)
2. Query recent items (GSI scan)
3. Aggregate sentiment distribution (client-side)
4. Tag match counts (client-side)

**Cost**: ~$0.35/month for demo scale (on-demand billing)

**Next Artifact**: contracts/ - API contracts for Lambda handlers
