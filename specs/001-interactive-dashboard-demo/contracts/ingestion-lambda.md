# Ingestion Lambda - Contract

**Handler**: `src/lambdas/ingestion/handler.lambda_handler`
**Trigger**: EventBridge Scheduler (every 5 minutes)
**Purpose**: Fetch items from NewsAPI matching watch tags, deduplicate, trigger sentiment analysis

**Updated**: 2025-11-17 - Regional Multi-AZ architecture

---

## Data Routing

**Write Target**: `sentiment-items` (single table, us-east-1)
- Write to single DynamoDB table
- Multi-AZ replication automatic (AWS-managed)
- Point-in-time recovery enabled (35 days)

**Read Operations**: Deduplication check only (conditional write)

---

## Input Event

### EventBridge Scheduled Event

```json
{
  "version": "0",
  "id": "cdc73f9d-aea9-11e3-9d5a-835b769c0d9c",
  "detail-type": "Scheduled Event",
  "source": "aws.events",
  "account": "123456789012",
  "time": "2025-11-16T14:30:00Z",
  "region": "us-east-1",
  "resources": [
    "arn:aws:events:us-east-1:123456789012:rule/sentiment-ingestion-scheduler"
  ],
  "detail": {}
}
```

**Note**: Event details are ignored; handler reads watch tags from DynamoDB config table (future) or environment variable.

---

## Configuration

### Environment Variables

| Variable | Description | Example |
|---|---|---|
| `WATCH_TAGS` | Comma-separated tags to monitor | `"AI,climate,economy,health,sports"` |
| `DYNAMODB_TABLE` | DynamoDB table name | `"sentiment-items"` |
| `NEWSAPI_SECRET_ARN` | Secrets Manager ARN for NewsAPI key | `"arn:aws:secretsmanager:..."` |
| `MODEL_VERSION` | Current model version | `"v1.0.0"` |
| `SNS_ANALYSIS_TOPIC_ARN` | SNS topic for analysis triggers | `"arn:aws:sns:..."` |

---

## Processing Logic

### Workflow

```
1. Read WATCH_TAGS from environment
2. Fetch NewsAPI key from Secrets Manager
3. For each tag:
   a. Call NewsAPI /everything endpoint
   b. Parse response articles
   c. For each article:
      - Generate source_id (newsapi#{article_hash})
      - Check if exists in DynamoDB (deduplication)
      - If new:
        * Insert raw item into DynamoDB (status=pending)
        * Publish SNS message to analysis topic
4. Log metrics (items fetched, new items, duplicates skipped)
5. Return summary
```

### Deduplication Strategy

```python
import hashlib

def generate_source_id(article: dict) -> str:
    """
    Generate stable source_id from article URL or content.
    Format: newsapi#{hash}
    """
    # Prefer URL (stable identifier)
    if article.get('url'):
        identifier = article['url']
    else:
        # Fallback: hash title + published_at
        identifier = f"{article['title']}#{article['publishedAt']}"

    # SHA256 hash (first 16 chars for brevity)
    hash_obj = hashlib.sha256(identifier.encode())
    hash_str = hash_obj.hexdigest()[:16]

    return f"newsapi#{hash_str}"
```

---

## Output

### Success Response

```json
{
  "statusCode": 200,
  "body": {
    "summary": {
      "tags_processed": 5,
      "articles_fetched": 487,
      "new_items": 23,
      "duplicates_skipped": 464,
      "errors": 0
    },
    "per_tag_stats": {
      "AI": {
        "fetched": 100,
        "new": 8,
        "duplicates": 92
      },
      "climate": {
        "fetched": 97,
        "new": 5,
        "duplicates": 92
      }
      // ... other tags
    },
    "execution_time_ms": 3421
  }
}
```

### Error Response

```json
{
  "statusCode": 500,
  "body": {
    "error": "NewsAPI rate limit exceeded",
    "code": "RATE_LIMIT_EXCEEDED",
    "details": {
      "retry_after_seconds": 3600,
      "tags_completed": 2,
      "tags_failed": 3
    }
  }
}
```

---

## DynamoDB Operations

### Insert New Item (Conditional Write)

```python
import boto3
import os
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])

def insert_pending_item(article: dict, source_id: str, matched_tags: list[str]) -> bool:
    """
    Insert item with status=pending if source_id doesn't exist.
    Returns True if inserted, False if duplicate.

    Uses conditional PutItem to ensure deduplication.
    """
    try:
        table.put_item(
            Item={
                'source_id': {'S': source_id},
                'ingested_at': {'S': datetime.utcnow().isoformat() + 'Z'},
                'source_type': {'S': 'newsapi'},
                'source_url': {'S': article.get('url', '')},
                'text_snippet': {'S': article.get('description', '')[:200]},
                'status': {'S': 'pending'},  # Will be updated by analysis lambda
                'matched_tags': {'SS': matched_tags},
                'metadata': {
                    'M': {
                        'title': {'S': article.get('title', '')},
                        'author': {'S': article.get('author', 'Unknown')},
                        'published_at': {'S': article.get('publishedAt', '')},
                        'source_name': {'S': article.get('source', {}).get('name', '')}
                    }
                }
            },
            ConditionExpression='attribute_not_exists(source_id)'
        )
        return True
    except dynamodb.exceptions.ConditionalCheckFailedException:
        # Duplicate, skip
        return False
```

---

## SNS Message (Analysis Trigger)

### Message Format

```json
{
  "source_id": "newsapi#a3f4e9d2c1b8a7f6",
  "source_type": "newsapi",
  "text_for_analysis": "Article description or content snippet...",
  "model_version": "v1.0.0",
  "matched_tags": ["AI", "technology"],
  "timestamp": "2025-11-16T14:30:15.000Z"
}
```

**Published to**: `arn:aws:sns:us-east-1:123456789012:sentiment-analysis-requests`

---

## NewsAPI Integration

### API Call

```python
import requests
import json

def fetch_newsapi_articles(api_key: str, tag: str, page_size: int = 100) -> list[dict]:
    """
    Fetch articles from NewsAPI /everything endpoint.
    """
    url = "https://newsapi.org/v2/everything"

    params = {
        'q': tag,
        'apiKey': api_key,
        'pageSize': page_size,
        'sortBy': 'publishedAt',
        'language': 'en',
        'from': (datetime.utcnow() - timedelta(hours=12)).isoformat()  # Last 12 hours
    }

    response = requests.get(url, params=params, timeout=10)

    if response.status_code == 429:
        # Rate limited
        raise RateLimitException(retry_after=response.headers.get('Retry-After', 3600))

    response.raise_for_status()

    data = response.json()
    return data.get('articles', [])
```

### Rate Limit Handling

```python
class RateLimitException(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded, retry after {retry_after}s")

def lambda_handler(event, context):
    """
    Main handler with rate limit backoff.
    """
    try:
        # ... fetch articles
        pass
    except RateLimitException as e:
        # Log and return partial success
        logger.warning(f"Rate limited: {e}")

        # Publish CloudWatch metric for alarm
        cloudwatch = boto3.client('cloudwatch')
        cloudwatch.put_metric_data(
            Namespace='SentimentAnalyzer',
            MetricData=[{
                'MetricName': 'NewsAPIRateLimitHit',
                'Value': 1,
                'Unit': 'Count'
            }]
        )

        return {
            'statusCode': 429,
            'body': {
                'error': 'Rate limit exceeded',
                'retry_after': e.retry_after
            }
        }
```

---

## CloudWatch Metrics

### Custom Metrics Emitted

| Metric | Unit | Description |
|---|---|---|
| `ArticlesFetched` | Count | Total articles returned by NewsAPI |
| `NewItemsIngested` | Count | New items inserted to DynamoDB |
| `DuplicatesSkipped` | Count | Items skipped (already exist) |
| `NewsAPIRateLimitHit` | Count | Rate limit encounters |
| `IngestionErrors` | Count | Errors during ingestion |
| `ExecutionTimeMs` | Milliseconds | Total handler execution time |

### Logging

```python
import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def log_structured(level: str, message: str, **kwargs):
    """
    Emit structured JSON logs for CloudWatch Logs Insights.
    """
    log_entry = {
        'level': level,
        'message': message,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        **kwargs
    }

    if level == 'INFO':
        logger.info(json.dumps(log_entry))
    elif level == 'ERROR':
        logger.error(json.dumps(log_entry))
    elif level == 'WARNING':
        logger.warning(json.dumps(log_entry))
```

**Example log entry**:
```json
{
  "level": "INFO",
  "message": "Ingestion completed",
  "timestamp": "2025-11-16T14:30:18.234Z",
  "tags_processed": 5,
  "articles_fetched": 487,
  "new_items": 23,
  "execution_time_ms": 3421
}
```

---

## IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:*:table/sentiment-items"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:sentiment-analyzer/newsapi-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "arn:aws:sns:*:*:sentiment-analysis-requests"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "SentimentAnalyzer"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/sentiment-ingestion:*"
    }
  ]
}
```

---

## Error Handling

### Retry Strategy

- **NewsAPI timeout**: Retry with exponential backoff (3 attempts)
- **DynamoDB throttling**: Use boto3 built-in retry (default: 3 attempts)
- **SNS publish failure**: Log error, continue (analysis can be retriggered)

### Circuit Breaker

```python
from datetime import datetime, timedelta

# Simple in-memory circuit breaker (per Lambda container)
circuit_breaker = {
    'failures': 0,
    'last_failure': None,
    'open': False
}

def check_circuit_breaker():
    """
    Open circuit if 3+ failures in 5 minutes.
    """
    if circuit_breaker['open']:
        # Check if cool-down period passed (5 minutes)
        if datetime.utcnow() - circuit_breaker['last_failure'] > timedelta(minutes=5):
            circuit_breaker['open'] = False
            circuit_breaker['failures'] = 0
        else:
            raise Exception("Circuit breaker open, skipping execution")

def record_failure():
    circuit_breaker['failures'] += 1
    circuit_breaker['last_failure'] = datetime.utcnow()

    if circuit_breaker['failures'] >= 3:
        circuit_breaker['open'] = True
        logger.error("Circuit breaker opened after 3 failures")
```

---

## Testing

### Unit Test Example

```python
# tests/unit/test_ingestion_handler.py
import pytest
from moto import mock_dynamodb, mock_secretsmanager
from src.lambdas.ingestion.handler import lambda_handler, generate_source_id

@mock_dynamodb
@mock_secretsmanager
def test_ingestion_deduplication():
    # Setup mocks
    setup_mock_dynamodb()
    setup_mock_secrets()

    # Mock NewsAPI response (will need to patch requests.get)
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {
            'status': 'ok',
            'articles': [
                {
                    'title': 'Test Article',
                    'url': 'https://example.com/article1',
                    'description': 'Test description',
                    'publishedAt': '2025-11-16T10:00:00Z',
                    'source': {'name': 'Test Source'}
                }
            ]
        }

        # First invocation - should insert
        result1 = lambda_handler({}, {})
        assert result1['body']['new_items'] == 1

        # Second invocation - should skip duplicate
        result2 = lambda_handler({}, {})
        assert result2['body']['new_items'] == 0
        assert result2['body']['duplicates_skipped'] == 1

def test_source_id_generation():
    article = {
        'url': 'https://example.com/article',
        'title': 'Test',
        'publishedAt': '2025-11-16T10:00:00Z'
    }

    source_id1 = generate_source_id(article)
    source_id2 = generate_source_id(article)

    # Should be deterministic
    assert source_id1 == source_id2
    assert source_id1.startswith('newsapi#')
```

---

## Performance SLA

- **Execution time**: <30 seconds (target: 3-5 seconds for 5 tags)
- **Memory**: 512 MB
- **Timeout**: 60 seconds
- **Concurrency**: 1 (scheduled, no concurrent executions)

---

## Monitoring & Alarms

### CloudWatch Alarms

1. **High error rate**:
   - Metric: `IngestionErrors > 5` in 10 minutes
   - Action: SNS notification to ops team

2. **Rate limit hit**:
   - Metric: `NewsAPIRateLimitHit > 0`
   - Action: SNS notification, adjust polling interval

3. **Execution timeout**:
   - Metric: Lambda duration > 50 seconds
   - Action: SNS notification, investigate slow NewsAPI responses

4. **No new items for 1 hour**:
   - Metric: `NewItemsIngested = 0` for 6 consecutive executions
   - Action: Check if NewsAPI is down or tags are stale
