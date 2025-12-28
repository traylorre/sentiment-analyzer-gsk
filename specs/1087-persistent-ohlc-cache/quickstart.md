# Quickstart: Persistent OHLC Cache

**Feature**: 1087-persistent-ohlc-cache
**Time to implement**: See tasks.md for breakdown

## Prerequisites

- Python 3.13+
- AWS credentials configured (preprod environment)
- Terraform 1.5+
- LocalStack (for local testing)

## Local Development

### 1. Start LocalStack

```bash
cd /home/traylorre/projects/sentiment-analyzer-gsk
make localstack-up
```

### 2. Deploy DynamoDB Table Locally

```bash
make tf-init-local
make tf-apply-local
```

### 3. Run Unit Tests

```bash
pytest tests/unit/shared/cache/test_ohlc_persistent_cache.py -v
```

### 4. Run Integration Tests (LocalStack)

```bash
pytest tests/integration/test_ohlc_persistent_cache.py -v
```

## Key Files to Modify

| File | Change |
|------|--------|
| `infrastructure/terraform/modules/dynamodb/main.tf` | Add `ohlc-cache` table |
| `infrastructure/terraform/modules/dynamodb/outputs.tf` | Export table name/ARN |
| `infrastructure/terraform/modules/iam/main.tf` | Add Dashboard Lambda permissions |
| `infrastructure/terraform/main.tf` | Pass table name to Dashboard Lambda |
| `src/lambdas/shared/cache/ohlc_cache.py` | NEW: Persistent cache module |
| `src/lambdas/dashboard/ohlc.py` | Integrate L2 cache before adapters |
| `tests/unit/shared/cache/test_ohlc_persistent_cache.py` | NEW: Unit tests |

## Key Functions

### Using the Cache (in ohlc.py)

```python
from src.lambdas.shared.cache.ohlc_cache import get_cached_candles, put_cached_candles

# Check cache first
result = get_cached_candles(
    ticker="AAPL",
    source="tiingo",
    resolution="5m",
    start_time=datetime(2025, 12, 1),
    end_time=datetime(2025, 12, 31)
)

if result.cache_hit and not result.missing_ranges:
    return result.candles  # Fast path

# Fetch missing data from API
api_candles = await tiingo_adapter.get_ohlc(...)

# Write-through to cache
put_cached_candles(
    ticker="AAPL",
    source="tiingo",
    resolution="5m",
    candles=api_candles
)
```

### Market Hours Check

```python
from src.lambdas.shared.cache.ohlc_cache import is_market_open

if is_market_open():
    # Current candle needs fresh data
    fetch_from_api = True
else:
    # Market closed, serve from cache
    fetch_from_api = False
```

## Testing Strategy

### Unit Tests (moto)
- Mock DynamoDB with moto
- Test cache hit/miss scenarios
- Test write-through behavior
- Test market hours logic

### Integration Tests (LocalStack)
- Real DynamoDB operations
- End-to-end cache flow
- Range query performance

### E2E Tests (preprod)
- Full stack with real AWS
- Verify <100ms latency
- Verify 90%+ cache hit rate

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OHLC_CACHE_TABLE` | DynamoDB table name | `{env}-ohlc-cache` |
| `AWS_REGION` | AWS region | `us-east-1` |

## Success Criteria Verification

```bash
# Verify cache hit rate (after initial population)
curl -s "https://{dashboard-url}/api/v2/tickers/AAPL/ohlc?range=1M&resolution=D" | jq '.cache_hit'

# Verify latency (should be <100ms after cache warm)
time curl -s "https://{dashboard-url}/api/v2/tickers/AAPL/ohlc?range=1M"

# Verify no API calls on second request (check CloudWatch logs)
```

## Rollback Plan

If issues arise:
1. Disable cache read (environment variable toggle)
2. Frontend continues working via adapters
3. Cache can be rebuilt by re-fetching data
