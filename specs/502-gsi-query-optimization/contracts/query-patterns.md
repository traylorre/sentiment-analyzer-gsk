# Query Pattern Contracts: GSI Query Optimization

**Feature**: 502-gsi-query-optimization
**Date**: 2025-12-18

## Contract Overview

These contracts define the expected input/output for each GSI query pattern replacing scan operations.

---

## Contract 1: Get Active Tickers

**Module**: `src/lambdas/ingestion/handler.py`
**Function**: `_get_active_tickers(table: TableResource) -> list[str]`

### Input
```python
table.query(
    IndexName="by_entity_status",
    KeyConditionExpression="entity_type = :et AND status = :status",
    ExpressionAttributeValues={
        ":et": "CONFIGURATION",
        ":status": "active"
    },
    ProjectionExpression="tickers"
)
```

### Output
```python
# Success: List of ticker symbols
["AAPL", "GOOGL", "MSFT", ...]

# Empty: No active configurations
[]
```

### Pagination
- Must handle `LastEvaluatedKey` for large result sets
- Continue querying until no more pages

---

## Contract 2: Query Sentiment Items

**Module**: `src/lambdas/sse_streaming/polling.py`
**Function**: `_query_by_sentiment(table: TableResource, sentiment: str) -> list[dict]`

### Input
```python
table.query(
    IndexName="by_sentiment",
    KeyConditionExpression="sentiment = :sentiment",
    ExpressionAttributeValues={
        ":sentiment": sentiment  # "positive" | "neutral" | "negative"
    }
)
```

### Output
```python
# Success: List of sentiment item records
[
    {
        "source_id": "src-123",
        "timestamp": "2025-12-18T10:30:00Z",
        "sentiment": "positive",
        "score": 0.85,
        ...
    },
    ...
]

# Empty: No items with this sentiment
[]
```

### Pagination
- Must handle `LastEvaluatedKey`
- Consider adding `Limit` parameter for real-time polling

---

## Contract 3: Find Alerts by Ticker

**Module**: `src/lambdas/notification/alert_evaluator.py`
**Function**: `_find_alerts_by_ticker(table: TableResource, ticker: str) -> list[dict]`

### Input
```python
table.query(
    IndexName="by_entity_status",
    KeyConditionExpression="entity_type = :type AND status = :status",
    FilterExpression="ticker = :ticker",
    ExpressionAttributeValues={
        ":type": "ALERT_RULE",
        ":status": "active",
        ":ticker": ticker
    }
)
```

### Output
```python
# Success: List of alert rules for this ticker
[
    {
        "PK": "ALERT#uuid-123",
        "SK": "RULE",
        "ticker": "AAPL",
        "threshold": 0.8,
        "condition": "above",
        ...
    },
    ...
]

# Empty: No alerts for this ticker
[]
```

### Notes
- `ticker` is in FilterExpression since it's not part of the GSI key
- This is still efficient: partition narrowed by entity_type + status

---

## Contract 4: Get Users Due for Digest

**Module**: `src/lambdas/notification/digest_service.py`
**Function**: `get_users_due_for_digest(table: TableResource) -> list[dict]`

### Input
```python
table.query(
    IndexName="by_entity_status",
    KeyConditionExpression="entity_type = :et AND status = :status",
    ExpressionAttributeValues={
        ":et": "DIGEST_SETTINGS",
        ":status": "enabled"
    },
    ProjectionExpression="PK, SK, user_id, #t, timezone, include_all_configs, config_ids, last_sent",
    ExpressionAttributeNames={"#t": "time"}
)
```

### Output
```python
# Success: List of digest setting records
[
    {
        "PK": "USER#uuid-456",
        "SK": "DIGEST_SETTINGS",
        "user_id": "uuid-456",
        "time": "08:00",
        "timezone": "America/New_York",
        ...
    },
    ...
]

# Empty: No users with enabled digest settings
[]
```

---

## Contract 5: Get User by Email (Deprecated)

**Module**: `src/lambdas/dashboard/auth.py`
**Function**: `get_user_by_email(table: TableResource, email: str) -> User | None`

### Contract
```python
def get_user_by_email(table: TableResource, email: str) -> User | None:
    """
    DEPRECATED: Use get_user_by_email_gsi() instead.

    Raises:
        NotImplementedError: Always raised with guidance message
    """
    raise NotImplementedError(
        "get_user_by_email() is deprecated due to O(n) table scan. "
        "Use get_user_by_email_gsi() for O(1) lookup via the by_email GSI."
    )
```

### Migration Path
All callers should use `get_user_by_email_gsi()` which is already implemented and uses the `by_email` GSI.

---

## Test Mock Contracts

### Mock Pattern for table.query()

```python
def create_query_mock(items_by_index: dict[str, list[dict]]) -> MagicMock:
    """
    Create a mock that returns different items based on IndexName.

    Args:
        items_by_index: Map of IndexName -> list of items to return

    Returns:
        MagicMock configured for table.query()
    """
    def query_side_effect(**kwargs):
        index_name = kwargs.get("IndexName")
        items = items_by_index.get(index_name, [])
        return {"Items": items, "Count": len(items)}

    mock_table = MagicMock()
    mock_table.query.side_effect = query_side_effect
    return mock_table
```

### Mock Pattern for Pagination

```python
def create_paginated_query_mock(items: list[dict], page_size: int = 100) -> MagicMock:
    """
    Create a mock that simulates pagination with LastEvaluatedKey.
    """
    def query_side_effect(**kwargs):
        start_key = kwargs.get("ExclusiveStartKey")
        start_idx = 0 if not start_key else int(start_key.get("idx", 0))

        page = items[start_idx:start_idx + page_size]
        response = {"Items": page, "Count": len(page)}

        if start_idx + page_size < len(items):
            response["LastEvaluatedKey"] = {"idx": start_idx + page_size}

        return response

    mock_table = MagicMock()
    mock_table.query.side_effect = query_side_effect
    return mock_table
```
