# Stream Processor Lambda Contract

**Feature**: `001-interactive-dashboard-demo` | **Date**: 2025-11-17
**Purpose**: Transform and denormalize data from primary write table to read-optimized dashboard table

---

## Overview

The Stream Processor Lambda is triggered by DynamoDB Streams from `sentiment-items-primary` and transforms/denormalizes data into `sentiment-items-dashboard` for optimized dashboard queries.

**Key Responsibilities**:
1. Process DynamoDB Stream events in batches (up to 100 records)
2. Transform primary table schema to dashboard-optimized schema
3. Day-partition data for efficient time-range queries
4. Denormalize matched tags (one dashboard item per tag)
5. Set TTL for automatic cleanup after 7 days

---

## Input: DynamoDB Stream Event

**Trigger**: DynamoDB Streams from `sentiment-items-primary`
**Event Type**: `INSERT`, `MODIFY` (ignore `REMOVE`)
**Batch Size**: 100 records (configurable)
**Maximum Batching Window**: 5 seconds

### Sample Event Structure

```json
{
  "Records": [
    {
      "eventID": "1",
      "eventName": "INSERT",
      "eventVersion": "1.1",
      "eventSource": "aws:dynamodb",
      "awsRegion": "us-east-1",
      "dynamodb": {
        "ApproximateCreationDateTime": 1700148000,
        "Keys": {
          "source_id": { "S": "newsapi#bbc-news-ai-regulation-2025-11-16" },
          "ingested_at": { "S": "2025-11-16T14:30:15.000Z" }
        },
        "NewImage": {
          "source_id": { "S": "newsapi#bbc-news-ai-regulation-2025-11-16" },
          "ingested_at": { "S": "2025-11-16T14:30:15.000Z" },
          "source_type": { "S": "newsapi" },
          "source_url": { "S": "https://www.bbc.com/news/technology-12345678" },
          "text_snippet": { "S": "European Union announces sweeping AI regulation..." },
          "sentiment": { "S": "neutral" },
          "score": { "N": "0.72" },
          "model_version": { "S": "v1.0.0" },
          "matched_tags": { "SS": ["AI", "regulation", "europe"] },
          "status": { "S": "analyzed" },
          "metadata": {
            "M": {
              "author": { "S": "Jane Smith" },
              "title": { "S": "EU Announces AI Regulation Framework" },
              "published_at": { "S": "2025-11-16T10:00:00Z" },
              "source_name": { "S": "BBC News" }
            }
          }
        },
        "OldImage": null,
        "SequenceNumber": "111",
        "SizeBytes": 500,
        "StreamViewType": "NEW_AND_OLD_IMAGES"
      },
      "eventSourceARN": "arn:aws:dynamodb:us-east-1:123456789012:table/sentiment-items-primary/stream/2025-11-16T00:00:00.000"
    }
  ]
}
```

---

## Processing Logic

### 1. Filter Events

**Skip Conditions**:
- Event type is `REMOVE` (we only process inserts and updates)
- `status` field is `pending` (only process analyzed items)
- `NewImage` is missing required fields (`source_id`, `ingested_at`, `sentiment`, `score`)

### 2. Transform Schema

**Input** (Primary Table):
```python
{
  'source_id': 'newsapi#bbc-news-ai-regulation-2025-11-16',
  'ingested_at': '2025-11-16T14:30:15.000Z',
  'source_type': 'newsapi',
  'sentiment': 'neutral',
  'score': 0.72,
  'matched_tags': ['AI', 'regulation', 'europe'],
  'text_snippet': 'European Union announces...',
  'source_url': 'https://...',
  'status': 'analyzed'
}
```

**Output** (Dashboard Table):
```python
{
  'day_partition': '2025-11-16',  # Extracted from ingested_at
  'ingested_at': '2025-11-16T14:30:15.000Z',  # Unchanged
  'source_id': 'newsapi#bbc-news-ai-regulation-2025-11-16',
  'source_type': 'newsapi',
  'sentiment': 'neutral',
  'score': 0.72,
  'sentiment_score_combined': 'neutral#0.72',  # New field for GSI
  'matched_tags': ['AI', 'regulation', 'europe'],  # StringSet
  'text_snippet': 'European Union announces...',
  'source_url': 'https://...',
  'expires_at': 1731859200  # Unix timestamp (now + 7 days)
}
```

### 3. Denormalize Tags

For each matched tag, create a separate item in the dashboard table:

```python
# Base item (as above)
base_item = {...}

# Write base item
dashboard_table.put_item(Item=base_item)

# Create one item per tag for by_tag GSI
for tag in matched_tags:
    tag_item = base_item.copy()
    tag_item['tag'] = tag  # Add tag attribute for GSI
    dashboard_table.put_item(Item=tag_item)
```

**Result**: 1 item with tags ['AI', 'regulation', 'europe'] produces:
- 1 base item (queryable by day_partition)
- 3 tag items (queryable by tag='AI', tag='regulation', tag='europe')
- Total: 4 items in dashboard table per 1 item in primary table

### 4. Set TTL for Auto-Cleanup

```python
from datetime import datetime, timedelta

def calculate_ttl(days=7):
    """Calculate Unix timestamp for TTL (7 days from now)"""
    expires_at = datetime.utcnow() + timedelta(days=days)
    return int(expires_at.timestamp())
```

---

## Output: DynamoDB Writes to Dashboard Table

**Target Table**: `sentiment-items-dashboard`

**Write Operations**:
- Base item: 1 `PutItem` per stream record
- Tag items: N `PutItem` operations (where N = number of matched tags)
- Total writes: 1 + N per stream record

**Batch Write Optimization** (Phase 2):
```python
# Use BatchWriteItem for better throughput
batch_writer = dashboard_table.batch_writer()

with batch_writer:
    batch_writer.put_item(Item=base_item)
    for tag in matched_tags:
        tag_item = base_item.copy()
        tag_item['tag'] = tag
        batch_writer.put_item(Item=tag_item)
```

---

## Error Handling

### 1. Retryable Errors

**Conditions**:
- `ProvisionedThroughputExceededException` (DynamoDB throttling)
- `InternalServerError` (temporary AWS service issue)
- Network timeouts

**Retry Strategy**:
- Lambda automatic retry: 3 attempts
- Exponential backoff: 1s, 2s, 4s
- If all retries fail: Poison message sent to DLQ (Dead Letter Queue)

### 2. Non-Retryable Errors

**Conditions**:
- Missing required fields in stream record
- Invalid timestamp format
- Malformed DynamoDB item

**Handling**:
- Log error with full context (record ID, source_id, error message)
- Skip record and continue processing batch
- Emit CloudWatch metric: `StreamProcessorErrors`

### 3. Partial Batch Failures

**Lambda Configuration**:
```hcl
bisect_batch_on_function_error = true
```

**Behavior**:
- If batch processing fails, Lambda splits batch in half
- Retries each half separately
- Isolates failing records without blocking entire batch

---

## Implementation

### Lambda Handler

```python
import boto3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
dashboard_table = dynamodb.Table('sentiment-items-dashboard')

def lambda_handler(event, context):
    """
    Process DynamoDB Stream events from sentiment-items-primary.
    Transform and denormalize into sentiment-items-dashboard.
    """
    processed_count = 0
    error_count = 0

    for record in event['Records']:
        try:
            # Skip DELETE events
            if record['eventName'] == 'REMOVE':
                continue

            new_image = record['dynamodb'].get('NewImage')
            if not new_image:
                logger.warning(f"Skipping record {record['eventID']}: No NewImage")
                continue

            # Skip if still pending analysis
            status = new_image.get('status', {}).get('S')
            if status != 'analyzed':
                logger.info(f"Skipping record {record['eventID']}: status={status}")
                continue

            # Extract and validate required fields
            source_id = new_image.get('source_id', {}).get('S')
            ingested_at = new_image.get('ingested_at', {}).get('S')
            sentiment = new_image.get('sentiment', {}).get('S')
            score = new_image.get('score', {}).get('N')

            if not all([source_id, ingested_at, sentiment, score]):
                logger.error(f"Missing required fields in record {record['eventID']}")
                error_count += 1
                continue

            # Transform to dashboard schema
            dashboard_item = transform_to_dashboard_schema(new_image)

            # Write base item
            dashboard_table.put_item(Item=dashboard_item)
            processed_count += 1

            # Denormalize tags
            matched_tags = new_image.get('matched_tags', {}).get('SS', [])
            for tag in matched_tags:
                tag_item = dashboard_item.copy()
                tag_item['tag'] = tag
                dashboard_table.put_item(Item=tag_item)
                processed_count += 1

        except Exception as e:
            logger.error(f"Error processing record {record['eventID']}: {str(e)}")
            error_count += 1
            # Continue processing remaining records

    # Log summary
    logger.info(f"Processed {processed_count} items with {error_count} errors")

    # Emit CloudWatch metrics
    cloudwatch = boto3.client('cloudwatch')
    cloudwatch.put_metric_data(
        Namespace='SentimentAnalyzer',
        MetricData=[
            {
                'MetricName': 'StreamProcessorSuccess',
                'Value': processed_count,
                'Unit': 'Count'
            },
            {
                'MetricName': 'StreamProcessorErrors',
                'Value': error_count,
                'Unit': 'Count'
            }
        ]
    )

    # Return success (errors logged but don't fail Lambda)
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': processed_count,
            'errors': error_count
        })
    }


def transform_to_dashboard_schema(new_image: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform primary table item to dashboard table schema.

    Args:
        new_image: DynamoDB stream record NewImage

    Returns:
        Dashboard table item (Python dict)
    """
    # Extract fields from DynamoDB JSON format
    source_id = new_image['source_id']['S']
    ingested_at = new_image['ingested_at']['S']
    source_type = new_image['source_type']['S']
    sentiment = new_image['sentiment']['S']
    score = float(new_image['score']['N'])
    matched_tags = set(new_image.get('matched_tags', {}).get('SS', []))
    text_snippet = new_image.get('text_snippet', {}).get('S', '')
    source_url = new_image.get('source_url', {}).get('S', '')

    # Calculate day partition from timestamp
    day_partition = ingested_at[:10]  # "2025-11-16"

    # Create combined sentiment+score key for GSI
    sentiment_score_combined = f"{sentiment}#{score:.2f}"

    # Calculate TTL (7 days from now)
    expires_at = int((datetime.utcnow() + timedelta(days=7)).timestamp())

    # Return transformed item (Python dict, boto3 handles type conversion)
    return {
        'day_partition': day_partition,
        'ingested_at': ingested_at,
        'source_id': source_id,
        'source_type': source_type,
        'sentiment': sentiment,
        'score': score,
        'sentiment_score_combined': sentiment_score_combined,
        'matched_tags': matched_tags,
        'text_snippet': text_snippet,
        'source_url': source_url,
        'expires_at': expires_at
    }
```

---

## Lambda Configuration

### Environment Variables

```hcl
environment {
  variables = {
    DASHBOARD_TABLE_NAME = "sentiment-items-dashboard"
    TTL_DAYS             = "7"
    LOG_LEVEL            = "INFO"
  }
}
```

### IAM Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetRecords",
        "dynamodb:GetShardIterator",
        "dynamodb:DescribeStream",
        "dynamodb:ListStreams"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:*:table/sentiment-items-primary/stream/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:BatchWriteItem"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:*:table/sentiment-items-dashboard"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:*:log-group:/aws/lambda/stream-processor:*"
    }
  ]
}
```

### Resource Limits

```hcl
resource "aws_lambda_function" "stream_processor" {
  function_name = "sentiment-stream-processor"
  runtime       = "python3.11"
  handler       = "handler.lambda_handler"
  timeout       = 60  # 1 minute (process 100 records)
  memory_size   = 512  # MB

  reserved_concurrent_executions = 10  # Limit concurrency to prevent dashboard table throttling

  dead_letter_config {
    target_arn = aws_sqs_queue.stream_processor_dlq.arn
  }
}
```

---

## Monitoring & Alarms

### CloudWatch Metrics

**Custom Metrics** (emitted by Lambda):
- `StreamProcessorSuccess`: Count of successfully processed items
- `StreamProcessorErrors`: Count of failed items
- `StreamProcessorBatchSize`: Number of records per invocation

**AWS-Provided Metrics**:
- `IteratorAge`: Stream processing lag (should be < 1 minute)
- `Errors`: Lambda invocation failures
- `Duration`: Processing time per batch

### CloudWatch Alarms

```hcl
resource "aws_cloudwatch_metric_alarm" "stream_lag" {
  alarm_name          = "stream-processor-lag-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "IteratorAge"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Maximum"
  threshold           = 60000  # 1 minute in milliseconds
  alarm_description   = "Stream processing is lagging behind"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.stream_processor.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "stream_errors" {
  alarm_name          = "stream-processor-errors-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "StreamProcessorErrors"
  namespace           = "SentimentAnalyzer"
  period              = 300  # 5 minutes
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "High error rate in stream processor"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_stream_processor.py
import pytest
from datetime import datetime, timedelta
from handler import transform_to_dashboard_schema, calculate_ttl

def test_transform_to_dashboard_schema():
    """Test schema transformation"""
    new_image = {
        'source_id': {'S': 'newsapi#test-123'},
        'ingested_at': {'S': '2025-11-16T14:30:15.000Z'},
        'source_type': {'S': 'newsapi'},
        'sentiment': {'S': 'positive'},
        'score': {'N': '0.85'},
        'matched_tags': {'SS': ['AI', 'tech']},
        'text_snippet': {'S': 'Sample text'},
        'source_url': {'S': 'https://example.com'}
    }

    result = transform_to_dashboard_schema(new_image)

    assert result['day_partition'] == '2025-11-16'
    assert result['sentiment_score_combined'] == 'positive#0.85'
    assert result['matched_tags'] == {'AI', 'tech'}
    assert 'expires_at' in result

def test_ttl_calculation():
    """Test TTL calculation"""
    ttl = calculate_ttl(days=7)
    expected = (datetime.utcnow() + timedelta(days=7)).timestamp()

    # Allow 1 second tolerance
    assert abs(ttl - expected) < 1
```

### Integration Tests

```python
# tests/integration/test_stream_processor_integration.py
import boto3
from moto import mock_dynamodb
import json

@mock_dynamodb
def test_stream_processor_end_to_end():
    """Test full stream processing flow"""
    # Setup mock tables
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')

    # Create dashboard table
    dynamodb.create_table(
        TableName='sentiment-items-dashboard',
        KeySchema=[
            {'AttributeName': 'day_partition', 'KeyType': 'HASH'},
            {'AttributeName': 'ingested_at', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'day_partition', 'AttributeType': 'S'},
            {'AttributeName': 'ingested_at', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # Simulate stream event
    event = {
        'Records': [
            {
                'eventName': 'INSERT',
                'dynamodb': {
                    'NewImage': {
                        'source_id': {'S': 'newsapi#test-123'},
                        'ingested_at': {'S': '2025-11-16T14:30:15.000Z'},
                        'source_type': {'S': 'newsapi'},
                        'sentiment': {'S': 'positive'},
                        'score': {'N': '0.85'},
                        'matched_tags': {'SS': ['AI', 'tech']},
                        'status': {'S': 'analyzed'}
                    }
                }
            }
        ]
    }

    # Invoke Lambda
    from handler import lambda_handler
    response = lambda_handler(event, None)

    # Verify dashboard table has items
    result = dynamodb.query(
        TableName='sentiment-items-dashboard',
        KeyConditionExpression='day_partition = :day',
        ExpressionAttributeValues={':day': {'S': '2025-11-16'}}
    )

    # Should have 1 base item + 2 tag items = 3 total
    assert result['Count'] == 3
```

---

## Performance Considerations

### Throughput Optimization

**Batch Size vs. Latency Trade-off**:
- Small batches (10 records): Lower latency (~1-2 sec), more Lambda invocations
- Large batches (100 records): Higher latency (~5-10 sec), fewer Lambda invocations
- **Recommended**: 100 records with 5-second batching window (balanced)

**Write Amplification**:
- 1 primary table item → 1 + N dashboard table items (N = matched tags)
- Demo scale: 5 tags average → 6x write amplification
- 500 writes/hour → 3,000 dashboard writes/hour
- **Cost impact**: $0.54/month (acceptable for demo)

### Concurrency Limits

**Problem**: Too many concurrent Lambda invocations can throttle dashboard table.

**Solution**: Reserved concurrency limit
```hcl
reserved_concurrent_executions = 10
```

**Calculation**:
- Dashboard table: On-demand capacity (scales automatically)
- But to prevent cost spikes: Limit Lambda to 10 concurrent executions
- Each execution writes ~100 base items + ~500 tag items = 600 writes
- Max throughput: 10 × 600 = 6,000 writes/batch (well below on-demand limits)

---

## Failure Scenarios & Recovery

### Scenario 1: Dashboard Table Unavailable

**Symptoms**: Lambda fails with `ResourceNotFoundException`

**Recovery**:
1. DynamoDB Streams retain records for 24 hours
2. Lambda automatic retry (3 attempts with exponential backoff)
3. If all retries fail: Records sent to DLQ
4. Once table available: Replay DLQ messages manually

### Scenario 2: Lambda Timeout (> 60 seconds)

**Symptoms**: Batch too large, processing exceeds timeout

**Recovery**:
1. `bisect_batch_on_function_error` splits batch in half
2. Each half retried separately
3. Isolates slow records without blocking entire stream

### Scenario 3: Duplicate Processing

**Cause**: Lambda retry processes same stream record twice

**Impact**: Duplicate items in dashboard table (same day_partition + ingested_at)

**Mitigation**:
- Use `PutItem` (not `UpdateItem`) → Overwrites duplicate with identical data
- No impact on dashboard queries (latest write wins)
- Consider adding conditional write in Phase 2: `attribute_not_exists(source_id)`

---

## Summary

**Function**: Transform primary table data to dashboard-optimized schema

**Trigger**: DynamoDB Streams (sentiment-items-primary)

**Processing**:
1. Filter for analyzed items only
2. Transform schema (add day_partition, sentiment_score_combined)
3. Denormalize tags (1 item → 1 + N items)
4. Set TTL for auto-cleanup

**Output**: 1 + N items per stream record written to sentiment-items-dashboard

**Performance**:
- Batch size: 100 records
- Batching window: 5 seconds
- Timeout: 60 seconds
- Concurrency: 10 (reserved)

**Cost** (demo scale): $0.02/month (Lambda invocations)

**Next Steps**:
1. Implement unit tests
2. Deploy Lambda with Terraform
3. Configure event source mapping with retries
4. Set up CloudWatch alarms for lag and errors
