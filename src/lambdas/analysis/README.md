# Analysis Lambda

## Purpose

Runs DistilBERT sentiment inference on articles, updates DynamoDB with results.

## Trigger

SNS topic: `${environment}-sentiment-analysis-requests`

## Flow

```
SNS → Lambda → Load Model → Inference → DynamoDB Update
                   ↓
            (/opt/model cache)
```

## For On-Call Engineers

### SOP Reference: SC-04 (Analysis Failures), SC-11 (High Latency)

**Alarms**:
- `${environment}-lambda-analysis-errors`
- `${environment}-analysis-latency-high`

### Quick Checks

```bash
# 1. Check recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-sentiment-analysis \
  --filter-pattern "ERROR" \
  --start-time $(date -d '30 minutes ago' +%s)000

# 2. Check inference latency
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-sentiment-analysis \
  --filter-pattern "InferenceLatencyMs" \
  --start-time $(date -d '1 hour ago' +%s)000

# 3. Check pending items (analysis backlog)
aws dynamodb query \
  --table-name dev-sentiment-items \
  --index-name by_status \
  --key-condition-expression "#s = :status" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":status": {"S": "pending"}}' \
  --select COUNT
```

### Common Failures

| Error Code | Cause | Fix |
|------------|-------|-----|
| `MODEL_LOAD_ERROR` | Model layer missing | Redeploy Lambda layer |
| `DATABASE_ERROR` | Conditional update failed | Check item exists with `pending` status |
| Timeout (30s) | Model too slow | Check Lambda memory (needs 1024MB) |

## Model Details

- **Model**: DistilBERT (distilbert-base-uncased-finetuned-sst-2-english)
- **Location**: `/opt/model` (Lambda layer)
- **Max tokens**: 512 (truncated)
- **Neutral threshold**: score < 0.6

## Idempotency

Uses conditional update: `attribute_not_exists(sentiment)`

This prevents re-processing already-analyzed items. If you need to force reanalysis,
update the item's `status` back to `pending` first.
