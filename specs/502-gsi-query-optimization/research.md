# Research: GSI Query Optimization

**Feature**: 502-gsi-query-optimization
**Date**: 2025-12-18

## Research Summary

This feature is a straightforward refactoring task - no unknowns or NEEDS CLARIFICATION items exist. All GSIs are already deployed and the query patterns are well-established in the codebase.

## Decision Log

### 1. GSI Query Pattern

**Decision**: Use `table.query()` with `IndexName` parameter and `KeyConditionExpression`

**Rationale**:
- Standard boto3 DynamoDB pattern already used in `get_user_by_email_gsi()` (auth.py:456-504)
- Provides O(1) partition lookup + O(log n) range key filtering
- Consistent with AWS best practices for DynamoDB access patterns

**Alternatives Considered**:
- PartiQL: Rejected - adds complexity without benefits for simple key lookups
- Scan with filter: Rejected - O(n) regardless of result size, higher read capacity cost

### 2. Pagination Handling

**Decision**: Implement `LastEvaluatedKey` loop for all GSI queries

**Rationale**:
- Some queries may return >1MB of data
- Ingestion handler already implements this pattern correctly
- Consistency across all modules

**Alternatives Considered**:
- Single query with Limit: Rejected - may miss results if more items exist
- DynamoDB paginators: Considered but manual loop is simpler and more explicit

### 3. Test Mock Strategy

**Decision**: Use function-based `side_effect` for `table.query()` mocks

**Rationale**:
- Allows repeatable query responses based on input parameters
- Matches existing test pattern in `test_email_uniqueness.py`
- Enables testing of pagination scenarios

**Alternatives Considered**:
- Static `return_value`: Rejected - doesn't support multiple query variations in same test
- Moto with real GSI: Possible but heavier setup, kept for integration tests

### 4. GSI Table Fixtures

**Decision**: Add GSI definitions to moto table creation in `conftest.py`

**Rationale**:
- Required for integration tests that create real moto tables
- Matches production Terraform GSI configuration
- Already have template in `test_email_uniqueness.py`

**Example Pattern**:
```python
GlobalSecondaryIndexes=[
    {
        "IndexName": "by_entity_status",
        "KeySchema": [
            {"AttributeName": "entity_type", "KeyType": "HASH"},
            {"AttributeName": "status", "KeyType": "RANGE"},
        ],
        "Projection": {"ProjectionType": "ALL"},
    },
]
```

### 5. Deprecation Pattern for get_user_by_email()

**Decision**: Raise `NotImplementedError` with guidance message

**Rationale**:
- Immediate failure is better than silent performance degradation
- Error message guides developers to correct function
- Function signature remains for compatibility during transition

**Implementation**:
```python
def get_user_by_email(table: TableResource, email: str) -> User | None:
    """DEPRECATED: Use get_user_by_email_gsi() instead for O(1) lookup."""
    raise NotImplementedError(
        "get_user_by_email() is deprecated. Use get_user_by_email_gsi() "
        "for O(1) lookup via the by_email GSI."
    )
```

## Existing GSI Definitions (from Terraform)

### sentiment_items table
| GSI Name | Hash Key | Range Key | Projection |
|----------|----------|-----------|------------|
| by_sentiment | sentiment | timestamp | ALL |
| by_tag | tag | timestamp | ALL |
| by_status | status | timestamp | KEYS_ONLY |

### feature_006_users table
| GSI Name | Hash Key | Range Key | Projection |
|----------|----------|-----------|------------|
| by_email | email | - | ALL |
| by_cognito_sub | cognito_sub | - | ALL |
| by_entity_status | entity_type | status | ALL |

## File-Specific Query Patterns

### 1. ingestion/handler.py - _get_active_tickers()

**Current (scan)**:
```python
response = table.scan(
    FilterExpression="entity_type = :et AND is_active = :active",
    ExpressionAttributeValues={":et": "CONFIGURATION", ":active": True},
)
```

**Target (query)**:
```python
response = table.query(
    IndexName="by_entity_status",
    KeyConditionExpression="entity_type = :et AND status = :status",
    ExpressionAttributeValues={":et": "CONFIGURATION", ":status": "active"},
)
```

### 2. sse_streaming/polling.py - _scan_table()

**Current (scan)**:
```python
response = table.scan(
    FilterExpression="begins_with(pk, :prefix)",
    ExpressionAttributeValues={":prefix": "SENTIMENT#"},
)
```

**Target (query)**:
```python
response = table.query(
    IndexName="by_sentiment",
    KeyConditionExpression="sentiment = :sentiment",
    ExpressionAttributeValues={":sentiment": sentiment_type},
)
```

### 3. notification/alert_evaluator.py - _find_alerts_by_ticker()

**Current (scan)**:
```python
response = table.scan(
    FilterExpression="entity_type = :type AND ticker = :ticker",
    ExpressionAttributeValues={":type": "ALERT_RULE", ":ticker": ticker},
)
```

**Target (query)**:
```python
response = table.query(
    IndexName="by_entity_status",
    KeyConditionExpression="entity_type = :type AND status = :status",
    FilterExpression="ticker = :ticker",
    ExpressionAttributeValues={":type": "ALERT_RULE", ":status": "active", ":ticker": ticker},
)
```

### 4. notification/digest_service.py - get_users_due_for_digest()

**Current (scan)**:
```python
response = table.scan(
    FilterExpression="entity_type = :et AND enabled = :enabled",
    ExpressionAttributeValues={":et": "DIGEST_SETTINGS", ":enabled": True},
)
```

**Target (query)**:
```python
response = table.query(
    IndexName="by_entity_status",
    KeyConditionExpression="entity_type = :et AND status = :status",
    ExpressionAttributeValues={":et": "DIGEST_SETTINGS", ":status": "enabled"},
)
```

### 5. dashboard/auth.py - get_user_by_email()

**Current (scan)**:
```python
response = table.scan(
    FilterExpression="email = :email AND entity_type = :type",
    ExpressionAttributeValues={":email": email.lower(), ":type": "USER"},
)
```

**Target**: Raise `NotImplementedError` - callers should use existing `get_user_by_email_gsi()`

## Reference Implementation

Branch `2-remove-scan-fallbacks` contains a working implementation but is behind main. Key patterns to extract:
- Pagination handling with LastEvaluatedKey
- Error handling for missing GSI (ResourceNotFoundException)
- Test mock patterns for table.query()

## No Outstanding Clarifications

All technical decisions are resolved. Ready for Phase 1 design artifacts.
