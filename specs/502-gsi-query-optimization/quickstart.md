# Quickstart: GSI Query Optimization

**Feature**: 502-gsi-query-optimization
**Date**: 2025-12-18

## Overview

Replace DynamoDB `table.scan()` calls with `table.query()` using existing GSIs for O(result) performance.

## Prerequisites

- Python 3.13
- boto3>=1.34.0
- pytest>=7.4.3, moto>=4.2.0 (for testing)
- GSIs already deployed (verified in Terraform)

## Implementation Pattern

### Before (Scan - O(table))
```python
response = table.scan(
    FilterExpression="entity_type = :type",
    ExpressionAttributeValues={":type": "CONFIGURATION"}
)
items = response.get("Items", [])
```

### After (Query - O(result))
```python
response = table.query(
    IndexName="by_entity_status",
    KeyConditionExpression="entity_type = :type AND status = :status",
    ExpressionAttributeValues={":type": "CONFIGURATION", ":status": "active"}
)
items = response.get("Items", [])
```

## Files to Modify

| File | Function | GSI |
|------|----------|-----|
| `src/lambdas/ingestion/handler.py` | `_get_active_tickers()` | by_entity_status |
| `src/lambdas/sse_streaming/polling.py` | `_scan_table()` → `_query_by_sentiment()` | by_sentiment |
| `src/lambdas/notification/alert_evaluator.py` | `_find_alerts_by_ticker()` | by_entity_status |
| `src/lambdas/notification/digest_service.py` | `get_users_due_for_digest()` | by_entity_status |
| `src/lambdas/dashboard/auth.py` | `get_user_by_email()` | Deprecate |

## Test Updates

1. **Change mock target**: `table.scan` → `table.query`
2. **Add GSI to fixtures**: Include `GlobalSecondaryIndexes` in moto table creation
3. **Use side_effect**: Enable different responses per query

### Example Test Mock
```python
def test_get_active_tickers_uses_gsi(mock_table):
    mock_table.query.return_value = {
        "Items": [{"tickers": ["AAPL", "GOOGL"]}],
        "Count": 1
    }

    result = _get_active_tickers(mock_table)

    # Verify GSI was used
    call_kwargs = mock_table.query.call_args.kwargs
    assert call_kwargs["IndexName"] == "by_entity_status"
    assert result == ["AAPL", "GOOGL"]
```

## Verification

```bash
# Run unit tests
pytest tests/unit/lambdas/ingestion/ -v
pytest tests/unit/lambdas/sse_streaming/ -v
pytest tests/unit/lambdas/notification/ -v
pytest tests/unit/lambdas/dashboard/ -v

# Verify no scan() calls remain (except chaos.py)
grep -r "\.scan(" src/lambdas/ --include="*.py" | grep -v chaos.py

# Full validation
make validate
make test-local
```

## Exception

`src/lambdas/dashboard/chaos.py` is allowed to retain `table.scan(Limit=100)` for admin debugging.

## Success Metrics

- [ ] All 5 target files use GSI queries
- [ ] All unit tests pass with query mocks
- [ ] No production scan() calls (except chaos.py)
- [ ] Code passes lint/format checks
