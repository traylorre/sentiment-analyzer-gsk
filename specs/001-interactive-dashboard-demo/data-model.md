# Data Model: Interactive Dashboard Demo

**Feature**: `001-interactive-dashboard-demo` | **Date**: 2025-11-16 (Updated: 2025-11-17)

## Purpose

Define the DynamoDB schema, access patterns, and data validation rules for the sentiment analysis demo with production-grade redundancy strategy.

## Architecture Overview

This implementation uses a **"Best of All Worlds" multi-tier redundancy strategy**:

1. **Primary Write Table** (`sentiment-items-primary`) - Write-optimized, no GSIs
2. **Global Table Replicas** - Multi-region disaster recovery
3. **DynamoDB Streams** - Real-time change data capture
4. **Read-Optimized Table** (`sentiment-items-dashboard`) - Denormalized for fast queries
5. **DAX Cache** (Phase 2) - Sub-10ms read performance

```
┌─────────────────────────────────────────────────────────────────┐
│                WRITE PATH (us-east-1 Primary)                   │
│  Ingestion Lambda ──► sentiment-items-primary                   │
│  Analysis Lambda  ──►   • Strong consistency writes             │
│                         • No GSIs (optimized for writes)        │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ├─► Global Table Replication (Strategy 1)
                  │   ├─► us-west-2 replica (West Coast reads)
                  │   ├─► eu-west-1 replica (Europe reads)
                  │   └─► ap-south-1 replica (Asia reads)
                  │
                  └─► DynamoDB Streams (Strategy 2)
                        ↓
                  Stream Processor Lambda
                  • Transforms data
                  • Pre-computes aggregations
                  • Denormalizes for queries
                        ↓
            sentiment-items-dashboard (read-optimized)
            • Day-partitioned for efficient queries
            • Multiple GSIs for dashboard views
            • TTL for automatic cleanup (7 days)
                        ↓
                  DAX Cache (Phase 2 - optional)
                  • 3-node cluster (HA)
                  • 5-minute TTL
                  • Sub-10ms reads
                        ↓
            Dashboard Lambda (<10ms reads)
```

---

## Table 1: Primary Write Table (`sentiment-items-primary`)

**Purpose**: Write-optimized table for ingestion and analysis operations. No GSIs to minimize write latency and cost.

**Partition Key (PK)**: `source_id` (String)
- Format: `{source_type}#{stable_id}`
- Examples:
  - `newsapi#article-abc123`
  - `twitter#tweet-456789`
- Purpose: Unique identifier for deduplication

**Sort Key (SK)**: `ingested_at` (String)
- Format: ISO8601 timestamp (`2025-11-16T14:30:00.000Z`)
- Purpose: Time-ordered retrieval, enables "recent items" queries

**Stream Configuration**:
- Stream enabled: `true`
- Stream view type: `NEW_AND_OLD_IMAGES` (for dashboard table sync)

**Global Table Replicas**:
- `us-west-2` - West Coast failover
- `eu-west-1` - Europe failover
- `ap-south-1` - Asia failover

### Attributes (Primary Table)

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
| `status` | String | Yes | Processing state | Enum: `pending`, `analyzed` |

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

**Write Operations**: This table receives all writes from Ingestion and Analysis Lambdas.

**Read Operations**: Only for deduplication checks and fallback queries.

---

## Table 2: Read-Optimized Dashboard Table (`sentiment-items-dashboard`)

**Purpose**: Denormalized table optimized for dashboard queries. Populated via DynamoDB Streams from primary table.

**Partition Key (PK)**: `day_partition` (String)
- Format: `YYYY-MM-DD` (e.g., `2025-11-16`)
- Purpose: Efficient queries for "items from today"

**Sort Key (SK)**: `ingested_at` (String)
- Format: ISO8601 timestamp
- Purpose: Time-ordered retrieval within partition

**TTL Configuration**:
- Attribute: `expires_at` (Number, Unix timestamp)
- Auto-delete items after 7 days (dashboard only shows recent data)

### Attributes (Dashboard Table)

| Attribute | Type | Required | Description |
|---|---|---|---|
| `day_partition` | String | Yes | PK: YYYY-MM-DD format |
| `ingested_at` | String | Yes | SK: ISO8601 timestamp |
| `source_id` | String | Yes | Original primary key (for joins) |
| `source_type` | String | Yes | Source adapter type |
| `sentiment` | String | Yes | Classification result |
| `score` | Number | Yes | Confidence score |
| `sentiment_score_combined` | String | Yes | GSI key: `{sentiment}#{score}` (e.g., `positive#0.85`) |
| `matched_tags` | StringSet | Yes | Watch tags that matched |
| `text_snippet` | String | No | First 200 chars |
| `source_url` | String | No | Original URL |
| `expires_at` | Number | Yes | TTL: Unix timestamp (current_time + 7 days) |

### Global Secondary Index (GSI): `by_sentiment`

**Purpose**: Query items by sentiment type, sorted by confidence score

**Partition Key**: `day_partition` (String)
**Sort Key**: `sentiment_score_combined` (String, format: `{sentiment}#{score}`)

**Projection**: ALL

**Access Pattern**:
```python
# Query positive sentiment items from today, sorted by highest score
response = dynamodb.query(
    TableName='sentiment-items-dashboard',
    IndexName='by_sentiment',
    KeyConditionExpression='day_partition = :day AND begins_with(sentiment_score_combined, :sent)',
    ExpressionAttributeValues={
        ':day': '2025-11-16',
        ':sent': 'positive#'
    },
    ScanIndexForward=False,  # Highest scores first
    Limit=20
)
```

### Global Secondary Index (GSI): `by_tag`

**Purpose**: Query items by tag (denormalized - one item per tag)

**Partition Key**: `tag` (String)
**Sort Key**: `ingested_at` (String)

**Projection**: ALL

**Note**: Stream processor creates **one dashboard item per matched tag** to enable efficient tag-based queries.

**Access Pattern**:
```python
# Get all items matching tag "AI" from last 24 hours
response = dynamodb.query(
    TableName='sentiment-items-dashboard',
    IndexName='by_tag',
    KeyConditionExpression='tag = :tag AND ingested_at > :cutoff',
    ExpressionAttributeValues={
        ':tag': 'AI',
        ':cutoff': (datetime.now() - timedelta(hours=24)).isoformat() + 'Z'
    },
    ScanIndexForward=False,
    Limit=20
)
```

---

## Table 3: DAX Cache Configuration (Phase 2 - Optional)

**Purpose**: In-memory caching layer for sub-10ms dashboard reads

**Cluster Configuration**:
- Node type: `dax.t3.small` (3 nodes for HA)
- Availability zones: `us-east-1a`, `us-east-1b`, `us-east-1c`
- Cache TTL: 300 seconds (5 minutes)

**Cached Tables**:
- `sentiment-items-dashboard` (all queries)

**Write-through**: Disabled (read-only cache, writes go to primary table)

**Cost (Phase 2)**:
- 3 nodes × $0.045/hour = $97/month
- Only enable when read traffic > 10 queries/sec

---

## Access Patterns & Consistency Model

### Consistency Strategy

**Strong Consistency Requirements**:
- ✅ Deduplication checks (write to primary table)
- ✅ Analysis Lambda updates (conditional write to prevent race conditions)

**Eventual Consistency Acceptable**:
- ✅ Dashboard queries (200-500ms lag acceptable)
- ✅ Metrics aggregation (5-minute staleness acceptable with DAX)
- ✅ Global table replication (< 1 second lag)

**Write-after-Read Scenarios**:
- ❌ NOT NEEDED: No use case requires immediate read after write
- Ingestion → Dashboard display can tolerate 500ms lag
- Analysis update → Dashboard refresh can tolerate 500ms lag

### 1. Insert New Item (Deduplication) - PRIMARY TABLE

**Target**: `sentiment-items-primary` (us-east-1 ONLY)

Use conditional write to prevent duplicate inserts:

```python
import boto3
from datetime import datetime

dynamodb = boto3.client('dynamodb', region_name='us-east-1')  # Always write to primary

def insert_item_if_new(item_data):
    """
    Insert item only if source_id doesn't exist (deduplication).
    Raises ConditionalCheckFailedException if duplicate.
    Writes to PRIMARY table only (not replicas, not dashboard table).
    """
    try:
        response = dynamodb.put_item(
            TableName='sentiment-items-primary',
            Item={
                'source_id': {'S': item_data['source_id']},
                'ingested_at': {'S': datetime.utcnow().isoformat() + 'Z'},
                'source_type': {'S': item_data['source_type']},
                'status': {'S': 'pending'},  # Analysis will update to 'analyzed'
                'sentiment': {'S': item_data.get('sentiment', 'neutral')},  # Placeholder
                'score': {'N': str(item_data.get('score', 0.5))},
                'model_version': {'S': item_data['model_version']},
                'matched_tags': {'SS': item_data['matched_tags']},
                'text_snippet': {'S': item_data.get('text_snippet', '')},
                'source_url': {'S': item_data.get('source_url', '')},
                'metadata': {'M': item_data.get('metadata', {})},
            },
            ConditionExpression='attribute_not_exists(source_id)'  # Dedup check
        )
        return True
    except dynamodb.exceptions.ConditionalCheckFailedException:
        # Item already exists, skip
        return False
```

### 2. Update with Sentiment Analysis Results - PRIMARY TABLE

**Target**: `sentiment-items-primary` (us-east-1 ONLY)

```python
def update_with_sentiment(source_id, ingested_at, sentiment, score, model_version):
    """
    Update item with sentiment analysis results.
    Only updates if status=pending (idempotent for SNS redelivery).
    """
    try:
        response = dynamodb.update_item(
            TableName='sentiment-items-primary',
            Key={
                'source_id': {'S': source_id},
                'ingested_at': {'S': ingested_at}
            },
            UpdateExpression='SET #status = :analyzed, sentiment = :sent, score = :score, model_version = :mv',
            ConditionExpression='#status = :pending',  # Only update pending items
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':pending': {'S': 'pending'},
                ':analyzed': {'S': 'analyzed'},
                ':sent': {'S': sentiment},
                ':score': {'N': str(score)},
                ':mv': {'S': model_version}
            }
        )
        return True
    except dynamodb.exceptions.ConditionalCheckFailedException:
        # Already analyzed (SNS redelivery), skip
        return False
```

### 3. Stream Processor Logic - TRANSFORMS PRIMARY → DASHBOARD

**Trigger**: DynamoDB Stream from `sentiment-items-primary`

**Transform Logic**:
```python
import boto3
from datetime import datetime, timedelta

dynamodb = boto3.resource('dynamodb')
dashboard_table = dynamodb.Table('sentiment-items-dashboard')

def lambda_handler(event, context):
    """
    Process DynamoDB stream events from primary table.
    Transform and denormalize into dashboard table.
    """
    for record in event['Records']:
        if record['eventName'] in ['INSERT', 'MODIFY']:
            new_image = record['dynamodb']['NewImage']

            # Skip if still pending analysis
            if new_image.get('status', {}).get('S') != 'analyzed':
                continue

            # Extract fields
            source_id = new_image['source_id']['S']
            ingested_at = new_image['ingested_at']['S']
            sentiment = new_image['sentiment']['S']
            score = float(new_image['score']['N'])
            matched_tags = new_image.get('matched_tags', {}).get('SS', [])

            # Calculate day partition
            day_partition = ingested_at[:10]  # "2025-11-16"

            # Combined sentiment+score key for GSI
            sentiment_score_combined = f"{sentiment}#{score:.2f}"

            # TTL: expire after 7 days
            expires_at = int((datetime.now() + timedelta(days=7)).timestamp())

            # Base item for dashboard table
            base_item = {
                'day_partition': day_partition,
                'ingested_at': ingested_at,
                'source_id': source_id,
                'source_type': new_image['source_type']['S'],
                'sentiment': sentiment,
                'score': score,
                'sentiment_score_combined': sentiment_score_combined,
                'matched_tags': matched_tags,
                'text_snippet': new_image.get('text_snippet', {}).get('S', ''),
                'source_url': new_image.get('source_url', {}).get('S', ''),
                'expires_at': expires_at
            }

            # Write main dashboard item
            dashboard_table.put_item(Item=base_item)

            # DENORMALIZATION: Create one item per tag for by_tag GSI
            for tag in matched_tags:
                tag_item = base_item.copy()
                tag_item['tag'] = tag  # Add tag attribute for GSI
                dashboard_table.put_item(Item=tag_item)
```

### 4. Query Recent Items (Dashboard) - DASHBOARD TABLE with DAX

**Target**: `sentiment-items-dashboard` (via DAX cache in Phase 2)

```python
import os
import amazondax  # Phase 2 only

# Phase 1: Direct DynamoDB query
dynamodb = boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Phase 2: DAX cache
# dax_endpoint = os.environ.get('DAX_ENDPOINT')
# dynamodb = amazondax.AmazonDaxClient(endpoint_url=dax_endpoint) if dax_endpoint else boto3.client('dynamodb')

def get_recent_items(limit=20):
    """
    Fetch last N items for dashboard display.
    Queries today's partition from dashboard table (not primary table).
    Phase 2: Reads from DAX cache (sub-10ms latency).
    """
    today = datetime.now().strftime('%Y-%m-%d')

    response = dynamodb.query(
        TableName='sentiment-items-dashboard',
        KeyConditionExpression='day_partition = :day',
        ExpressionAttributeValues={':day': {'S': today}},
        ScanIndexForward=False,  # Newest first
        Limit=limit,
        ConsistentRead=False  # Eventually consistent (acceptable for dashboard)
    )

    items = []
    for item in response['Items']:
        items.append({
            'source_id': item['source_id']['S'],
            'ingested_at': item['ingested_at']['S'],
            'sentiment': item['sentiment']['S'],
            'score': float(item['score']['N']),
            'text_snippet': item.get('text_snippet', {}).get('S', ''),
            'matched_tags': list(item.get('matched_tags', {}).get('SS', [])),
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

### Primary Write Table with Global Replication

```hcl
resource "aws_dynamodb_table" "sentiment_items_primary" {
  name           = "sentiment-items-primary"
  billing_mode   = "PAY_PER_REQUEST"  # On-demand for demo
  hash_key       = "source_id"
  range_key      = "ingested_at"

  # Enable streams for dashboard table sync
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  attribute {
    name = "source_id"
    type = "S"
  }

  attribute {
    name = "ingested_at"
    type = "S"
  }

  # NO GSIs on primary table (write-optimized)

  # Global Table Replicas (Phase 1 - optional, can defer to production)
  replica {
    region_name = "us-west-2"
  }

  replica {
    region_name = "eu-west-1"
  }

  replica {
    region_name = "ap-south-1"
  }

  # Server-side encryption
  server_side_encryption {
    enabled = true
  }

  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Environment = "demo"
    Feature     = "001-interactive-dashboard-demo"
    TableType   = "primary-write"
  }
}
```

### Read-Optimized Dashboard Table

```hcl
resource "aws_dynamodb_table" "sentiment_items_dashboard" {
  name           = "sentiment-items-dashboard"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "day_partition"
  range_key      = "ingested_at"

  attribute {
    name = "day_partition"
    type = "S"
  }

  attribute {
    name = "ingested_at"
    type = "S"
  }

  attribute {
    name = "sentiment_score_combined"
    type = "S"
  }

  attribute {
    name = "tag"
    type = "S"
  }

  # GSI: by_sentiment (for sentiment filtering)
  global_secondary_index {
    name            = "by_sentiment"
    hash_key        = "day_partition"
    range_key       = "sentiment_score_combined"
    projection_type = "ALL"
  }

  # GSI: by_tag (for tag-based queries)
  global_secondary_index {
    name            = "by_tag"
    hash_key        = "tag"
    range_key       = "ingested_at"
    projection_type = "ALL"
  }

  # TTL: Auto-delete items after 7 days
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  # Server-side encryption
  server_side_encryption {
    enabled = true
  }

  tags = {
    Environment = "demo"
    Feature     = "001-interactive-dashboard-demo"
    TableType   = "read-optimized-dashboard"
  }
}
```

### Stream Processor Lambda Trigger

```hcl
resource "aws_lambda_event_source_mapping" "stream_processor" {
  event_source_arn  = aws_dynamodb_table.sentiment_items_primary.stream_arn
  function_name     = aws_lambda_function.stream_processor.arn
  starting_position = "LATEST"

  # Batch configuration
  batch_size        = 100  # Process 100 records per invocation
  maximum_batching_window_in_seconds = 5  # Wait up to 5 seconds to accumulate batch

  # Error handling
  maximum_retry_attempts = 3
  bisect_batch_on_function_error = true  # Split batch if processing fails

  # Filter for analyzed items only (Phase 2 optimization)
  # filter_criteria {
  #   filter {
  #     pattern = jsonencode({
  #       dynamodb = {
  #         NewImage = {
  #           status = { S = ["analyzed"] }
  #         }
  #       }
  #     })
  #   }
  # }
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

**Cost Analysis: "Best of All Worlds" Architecture**

#### Phase 1 (Demo): Primary + Dashboard Tables + Global Replicas

| Component | Writes/Month | Reads/Month | Cost |
|-----------|--------------|-------------|------|
| **Primary table** (us-east-1) | 360,000 | 0 (dedup checks via conditional writes) | $0.09 |
| **Global replicas** (3 regions) | 360,000 × 3 = 1.08M (replication) | 0 (standby only) | $0.27 |
| **Stream processing** | N/A (included in primary table cost) | N/A | $0.00 |
| **Dashboard table writes** | 360,000 + (360k × 5 tags) = 2.16M | N/A | $0.54 |
| **Dashboard table reads** | N/A | 2 reads/s × 2.6M s = 5.2M | $0.26 |
| **Lambda (stream processor)** | N/A | N/A | $0.02 (360k invocations) |
| **Data transfer** | N/A | N/A | $0.01 (minimal) |
| **TOTAL (Phase 1)** | | | **$1.19/month** |

#### Phase 2 (Production): Add DAX Cache

| Additional Component | Cost |
|---------------------|------|
| **DAX cluster** (3 × dax.t3.small) | $97/month |
| **TOTAL (Phase 2)** | **$98.19/month** |

**Break-even Analysis**:
- DAX cost-effective when: Dashboard reads > 10 queries/second
- Current demo scale: 2 reads/second → **Defer DAX to production**

#### Phase 3 (High Scale): 10,000 writes/hour, 100 reads/second

| Component | Monthly Cost |
|-----------|-------------|
| Primary table writes | $7 |
| Global replicas (3 regions) | $21 |
| Dashboard table writes | $35 |
| Dashboard table reads | $20 |
| DAX cluster (3 × dax.r5.large) | $450 |
| Lambda (stream processor) | $5 |
| **TOTAL (Phase 3)** | **$538/month** |

**Cost Comparison (Phase 3 scale)**:
- Without "Best of All Worlds": DynamoDB alone = $2,000/month (100 reads/sec)
- **Savings with DAX + read table**: $1,462/month (73% reduction)

### Query Optimization

1. **Use Projection Expressions**: Fetch only needed attributes to reduce data transfer
2. **Limit Results**: Always set `Limit` parameter for dashboard queries
3. **Client-Side Aggregation**: Aggregate sentiment distribution in Lambda (not DynamoDB Scan)
4. **GSI Coverage**: Ensure all access patterns use GSI (avoid table scans)
5. **Day Partitioning**: Dashboard table partitioned by day for efficient range queries
6. **TTL Cleanup**: Auto-delete dashboard items > 7 days old (reduces storage cost)

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

### Architecture: "Best of All Worlds" Multi-Tier Redundancy

**Table 1: Primary Write Table** (`sentiment-items-primary`)
- PK: `source_id` (deduplication key)
- SK: `ingested_at` (time-ordered retrieval)
- GSIs: NONE (write-optimized)
- Streams: Enabled (NEW_AND_OLD_IMAGES)
- Global Replicas: us-west-2, eu-west-1, ap-south-1 (disaster recovery)

**Table 2: Read-Optimized Dashboard Table** (`sentiment-items-dashboard`)
- PK: `day_partition` (YYYY-MM-DD)
- SK: `ingested_at` (time-ordered within day)
- GSIs: `by_sentiment` (sentiment filtering), `by_tag` (tag queries)
- TTL: 7 days (auto-cleanup)
- Source: Populated via DynamoDB Streams from primary table

**Table 3: DAX Cache** (Phase 2 - Optional)
- Cluster: 3 nodes (HA)
- TTL: 5 minutes
- Target: Dashboard table only

**Access Patterns**:
1. **Write**: Insert to primary table (with deduplication)
2. **Update**: Analysis Lambda updates primary table (conditional)
3. **Stream**: Transform primary → dashboard table (denormalized)
4. **Read**: Dashboard Lambda queries dashboard table (or DAX cache)

**Consistency Model**:
- Strong consistency: Deduplication, analysis updates
- Eventual consistency: Dashboard reads (200-500ms lag acceptable)
- Global table replication: < 1 second lag

**Cost**:
- Phase 1 (Demo): **$1.19/month** (primary + replicas + dashboard table)
- Phase 2 (Add DAX): **$98/month** (enable when reads > 10/sec)
- Phase 3 (Production scale): **$538/month** (saves $1,462/month vs. DynamoDB alone)

**Traffic Interleaving Strategy**:
- Writes: Always to primary table (us-east-1)
- Reads: Dashboard table (us-east-1) or DAX cache
- Failover: Global replicas can be promoted if primary region fails
- Stream processing: Batched (100 records) with 5-second window to smooth traffic

**Next Artifacts**:
1. contracts/stream-processor-lambda.md - Stream processor specification
2. Updated contracts/ - API contracts for Lambda handlers with new table routing
3. infrastructure/terraform/ - Terraform configurations for all tables
