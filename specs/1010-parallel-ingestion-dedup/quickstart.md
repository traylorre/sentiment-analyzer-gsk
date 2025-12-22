# Quickstart: Parallel Ingestion with Cross-Source Deduplication

**Feature**: 1010-parallel-ingestion-dedup
**Date**: 2025-12-21

## Prerequisites

1. AWS credentials configured for preprod environment
2. Tiingo API key with News API access enabled
3. Finnhub API key
4. Python 3.13 with project dependencies installed

## Quick Test

### 1. Verify Tiingo API Access

```bash
# Get Tiingo key from Secrets Manager
TIINGO_KEY=$(aws secretsmanager get-secret-value \
  --secret-id preprod/sentiment-analyzer/tiingo \
  --query SecretString --output text | jq -r '.api_key')

# Test News API access
curl -s -H "Authorization: Token ${TIINGO_KEY}" \
  "https://api.tiingo.com/tiingo/news?tickers=AAPL&limit=1" | jq .
```

Expected: JSON array with article objects (HTTP 200)

### 2. Verify Finnhub API Access

```bash
# Get Finnhub key from Secrets Manager
FINNHUB_KEY=$(aws secretsmanager get-secret-value \
  --secret-id preprod/sentiment-analyzer/finnhub \
  --query SecretString --output text | jq -r '.api_key')

# Test News API access
curl -s "https://finnhub.io/api/v1/news?category=general&token=${FINNHUB_KEY}" | jq '.[0]'
```

Expected: JSON object with article fields (HTTP 200)

### 3. Run Unit Tests

```bash
cd /home/traylorre/projects/sentiment-analyzer-gsk

# Run dedup tests
pytest tests/unit/ingestion/test_cross_source_dedup.py -v

# Run parallel fetcher tests
pytest tests/unit/ingestion/test_parallel_fetcher.py -v

# Run all new tests
pytest tests/unit/ingestion/ tests/unit/shared/test_*_threadsafe.py -v
```

### 4. Trigger Manual Ingestion

```bash
# Invoke ingestion Lambda directly
aws lambda invoke \
  --function-name preprod-sentiment-ingestion \
  --payload '{"debug": true}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/ingestion-response.json

# View response
cat /tmp/ingestion-response.json | jq .
```

### 5. Check Collision Metrics

```bash
# Query recent articles with multi-source attribution
aws dynamodb scan \
  --table-name preprod-sentiment-items \
  --filter-expression "size(sources) > :one" \
  --expression-attribute-values '{":one": {"N": "1"}}' \
  --max-items 5 \
  --query 'Items[].{headline: headline.S, sources: sources.L}' | jq .
```

Expected: Articles with `sources: ["tiingo", "finnhub"]`

## Debug Commands

### View CloudWatch Logs

```bash
# Tail ingestion logs
aws logs tail /aws/lambda/preprod-sentiment-ingestion --since 10m --follow

# Search for collision events
aws logs filter-log-events \
  --log-group-name /aws/lambda/preprod-sentiment-ingestion \
  --filter-pattern "collision" \
  --start-time $(date -d '1 hour ago' +%s000)
```

### Check Dedup Key Generation

```python
# Python REPL test
from src.lambdas.ingestion.dedup import normalize_headline, generate_dedup_key

headline1 = "Apple Reports Q4 Earnings Beat - Reuters"
headline2 = "Apple reports Q4 earnings beat"

print(f"Normalized 1: {normalize_headline(headline1)}")
print(f"Normalized 2: {normalize_headline(headline2)}")
print(f"Keys match: {generate_dedup_key(headline1, '2025-12-21') == generate_dedup_key(headline2, '2025-12-21')}")
```

Expected: `Keys match: True`

### Verify Thread Safety

```bash
# Run thread safety stress tests
pytest tests/unit/shared/test_quota_tracker_threadsafe.py::test_concurrent_calls -v
pytest tests/unit/shared/test_circuit_breaker_threadsafe.py::test_concurrent_failures -v
```

## Success Criteria Verification

| Criterion | Verification Command | Expected |
|-----------|---------------------|----------|
| SC-001: Zero duplicates | `aws dynamodb scan --table-name preprod-sentiment-items --filter-expression "size(sources) > :one" --expression-attribute-values '{":one": {"N": "1"}}' --query 'Count'` | Count > 0 (collisions detected and merged) |
| SC-002: <500ms dedup | Check CloudWatch metrics for `DedupLatencyMs` | P99 < 500ms |
| SC-003: 15-25% collision rate | Check CloudWatch metrics for `CollisionRate` | 0.15 ≤ rate ≤ 0.25 |
| SC-004: Independent sources | Kill Tiingo mid-ingestion, verify Finnhub continues | No Finnhub errors |
| SC-005: Attribution tracking | Query multi-source article, check `source_attribution` | Both sources present |

## Common Issues

### Issue: "You do not have permission to access the News API"

**Cause**: Tiingo subscription doesn't include News API
**Fix**: Upgrade Tiingo plan at https://tiingo.com/account/api/token

### Issue: Race condition in quota tracker

**Symptom**: Inconsistent quota counts under load
**Fix**: Ensure using `ThreadSafeQuotaTracker` wrapper, not raw tracker

### Issue: Dedup key collision for different articles

**Symptom**: Unrelated articles merged together
**Fix**: Check headline normalization isn't too aggressive; review normalize_headline()

## Next Steps

After quickstart verification:

1. Run full test suite: `make test-local`
2. Run integration tests: `pytest tests/integration/ingestion/ -v`
3. Deploy to preprod: `gh workflow run deploy.yml -f environment=preprod`
4. Monitor collision metrics in CloudWatch dashboard
