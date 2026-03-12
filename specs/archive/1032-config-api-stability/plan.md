# Implementation Plan: Config API Stability

## Architecture Overview

```
                    ┌─────────────────┐
                    │   API Gateway   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  FastAPI Router │
                    │ (router_v2.py)  │
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │   Configuration Service     │
              │   (configurations.py)       │
              │                             │
              │  ┌───────────────────────┐  │
              │  │   Retry Decorator     │  │  ← NEW: Wrap retryable operations
              │  │   (tenacity)          │  │
              │  └───────────────────────┘  │
              │                             │
              │  ┌───────────────────────┐  │
              │  │ Conditional Write     │  │  ← NEW: Atomic limit enforcement
              │  │ (DynamoDB expression) │  │
              │  └───────────────────────┘  │
              └──────────────┬──────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼────┐        ┌─────▼─────┐       ┌─────▼─────┐
    │   S3    │        │ DynamoDB  │       │  Ticker   │
    │  Cache  │        │   Table   │       │  Validate │
    └─────────┘        └───────────┘       └───────────┘
```

## Implementation Phases

### Phase 1: Retry Infrastructure (P1)

Add retry logic for transient failures using `tenacity` library.

**Files Modified**:
- `src/lambdas/dashboard/configurations.py`
- `requirements.txt` (add tenacity if not present)

**Changes**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from botocore.exceptions import ClientError

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((ClientError,)),
    reraise=True
)
def _put_item_with_retry(table, item):
    """Put item with retry for transient DynamoDB errors."""
    table.put_item(Item=item)
```

### Phase 2: Conditional Writes for Atomicity (P2)

Replace count-then-write pattern with DynamoDB transactions or conditional expressions.

**Option A: Transaction (Preferred)**
```python
def create_configuration_atomic(user_id, config_data, max_configs=5):
    """Create config with atomic limit check using DynamoDB transactions."""
    client = boto3.client('dynamodb')

    # Transaction: Query count + Put item atomically
    response = client.transact_write_items(
        TransactItems=[
            {
                'Put': {
                    'TableName': table_name,
                    'Item': config_item,
                    'ConditionExpression': 'attribute_not_exists(PK)'
                }
            }
        ]
    )
```

**Option B: Conditional Expression (Simpler)**
```python
# Use a counter attribute in user record
# Check count < max in condition expression
table.put_item(
    Item=config_item,
    ConditionExpression='attribute_not_exists(PK) OR (attribute_exists(config_count) AND config_count < :max)',
    ExpressionAttributeValues={':max': max_configs}
)
```

### Phase 3: S3 Cache Resilience (P1)

Add retry and fallback for ticker cache loading.

**Files Modified**:
- `src/lambdas/shared/ticker_cache.py` (or create if needed)

**Changes**:
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((ClientError, BotoCoreError)),
)
def load_ticker_cache():
    """Load ticker cache with retry."""
    # ... existing S3 logic
```

**Fallback Strategy**:
1. Try S3 cache
2. On failure, try Lambda-local cache (bundled with deployment)
3. On failure, allow any ticker (log warning)

### Phase 4: Improved Error Responses (P3)

Map all error types to appropriate HTTP status codes.

**Error Mapping Table**:
| Exception Type | HTTP Status | Response |
|----------------|-------------|----------|
| ValidationError | 400 | Bad Request + details |
| ConditionalCheckFailedException | 409 | Conflict (limit reached) |
| ThrottlingException | 429 | Too Many Requests + Retry-After |
| ServiceException (S3/DynamoDB) | 503 | Service Unavailable + Retry-After |
| Timeout | 504 | Gateway Timeout |

## Testing Strategy

### Unit Tests
- Mock DynamoDB/S3 failures and verify retry behavior
- Test conditional write rejection (409 response)
- Test error mapping for all exception types

### Integration Tests
- LocalStack: Concurrent config creation (5 parallel requests)
- LocalStack: S3 failure simulation
- LocalStack: DynamoDB throttling simulation

### E2E Tests
- Verify all 17 skipped tests pass after changes
- Add explicit config creation success rate test

## Rollout Plan

1. **Deploy to preprod** with feature flag disabled
2. **Enable for 10% of requests** (gradual rollout)
3. **Monitor error rates** for 24 hours
4. **Full rollout** if error rate < 1%

## Dependencies

- `tenacity>=8.0.0` - Retry library (may already be in requirements)
- No new AWS services required
- No DynamoDB schema changes (conditional expressions work on existing schema)

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Retry adds latency | Medium | Low | Set max 3 retries, exponential backoff caps at 4s |
| Conditional write increases costs | Low | Low | Single extra expression, negligible WCU |
| Transaction conflicts | Low | Medium | Handle TransactionCanceledException gracefully |

## Estimated Effort

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: Retry | 2 hours | None |
| Phase 2: Conditional | 3 hours | Phase 1 |
| Phase 3: S3 Resilience | 2 hours | Phase 1 |
| Phase 4: Error Mapping | 1 hour | Phases 1-3 |
| Testing | 3 hours | All phases |
| **Total** | **~11 hours** | |
