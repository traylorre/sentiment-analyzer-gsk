# Quickstart: Self-Healing Ingestion

**Feature**: 1003-self-healing-ingestion
**Date**: 2025-12-20

## Overview

This feature adds automatic detection and reprocessing of stale pending items in the ingestion pipeline. Items stuck in "pending" status for more than 1 hour without a sentiment classification are automatically republished to the SNS topic for reanalysis.

## Problem Statement

Items ingested into DynamoDB may remain in "pending" status indefinitely if:
1. All articles in a batch were duplicates (no SNS publish triggered)
2. SNS publish failed during ingestion
3. Analysis Lambda failed to process the item

This causes the dashboard to show empty/stale data even when items exist in the database.

## Solution

Extend the ingestion Lambda to:
1. After normal ingestion, query for stale pending items (>1 hour old)
2. Republish stale items to the analysis SNS topic
3. Log counts for observability

## Quick Commands

### Check for Stale Items (Manual)

```bash
# Query DynamoDB for pending items older than 1 hour
THRESHOLD=$(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ)
aws dynamodb query \
  --table-name preprod-sentiment-items \
  --index-name by_status \
  --key-condition-expression "#s = :status AND #ts < :threshold" \
  --expression-attribute-names '{"#s": "status", "#ts": "timestamp"}' \
  --expression-attribute-values "{\":status\": {\"S\": \"pending\"}, \":threshold\": {\"S\": \"$THRESHOLD\"}}" \
  --select COUNT
```

### Trigger Ingestion Manually

```bash
# Invoke ingestion Lambda (includes self-healing check)
aws lambda invoke \
  --function-name preprod-sentiment-ingestion \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/ingestion-response.json

cat /tmp/ingestion-response.json | jq
```

### Check Self-Healing Logs

```bash
# View recent self-healing activity
aws logs filter-log-events \
  --log-group-name /aws/lambda/preprod-sentiment-ingestion \
  --filter-pattern "Self-healing" \
  --start-time $(date -d '1 hour ago' +%s000)
```

## Testing

### Unit Tests

```bash
# Run self-healing unit tests
python -m pytest tests/unit/lambdas/ingestion/test_self_healing.py -v
```

### Integration Test

```bash
# 1. Create a stale pending item manually
aws dynamodb put-item \
  --table-name preprod-sentiment-items \
  --item '{
    "source_id": {"S": "test:stale-item-123"},
    "timestamp": {"S": "2025-01-01T00:00:00Z"},
    "status": {"S": "pending"},
    "source_type": {"S": "test"},
    "text_for_analysis": {"S": "Test article for self-healing validation"}
  }'

# 2. Trigger ingestion
aws lambda invoke \
  --function-name preprod-sentiment-ingestion \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/out.json

# 3. Check logs for "Self-healing: republished 1 stale items"
aws logs filter-log-events \
  --log-group-name /aws/lambda/preprod-sentiment-ingestion \
  --filter-pattern "Self-healing" \
  --start-time $(date -d '5 minutes ago' +%s000)

# 4. Clean up test item
aws dynamodb delete-item \
  --table-name preprod-sentiment-items \
  --key '{"source_id": {"S": "test:stale-item-123"}}'
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SELF_HEALING_ENABLED` | `true` | Enable/disable self-healing |
| `SELF_HEALING_THRESHOLD_HOURS` | `1` | Hours before item is considered stale |
| `SELF_HEALING_BATCH_SIZE` | `100` | Max items to republish per run |

## Metrics

Monitor in CloudWatch under `SentimentAnalyzer` namespace:

- `SelfHealingItemsFound` - Number of stale items detected
- `SelfHealingItemsRepublished` - Number of items successfully republished

## Troubleshooting

### Items Still Not Analyzed After Self-Healing

1. Check Analysis Lambda is receiving SNS messages:
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/preprod-sentiment-analysis \
     --start-time $(date -d '10 minutes ago' +%s000)
   ```

2. Check SNS subscription is active:
   ```bash
   aws sns list-subscriptions-by-topic \
     --topic-arn arn:aws:sns:us-east-1:ACCOUNT:preprod-sentiment-analysis-requests
   ```

### Self-Healing Running Too Often

If items keep getting republished every run:
1. Check Analysis Lambda is successfully updating item status to "analyzed"
2. Check for Analysis Lambda errors in CloudWatch
3. Verify DynamoDB write permissions for Analysis Lambda
