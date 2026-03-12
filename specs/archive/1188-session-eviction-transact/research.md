# Research: DynamoDB TransactWriteItems for Session Eviction

**Feature**: 1188-session-eviction-transact
**Created**: 2026-01-10

## Decision Summary

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Transaction API | TransactWriteItems | All-or-nothing atomicity required |
| Blocklist key pattern | `BLOCK#refresh#{hash}` as PK, `BLOCK` as SK | Matches single-table design |
| Error handling | Catch TransactionCanceledException | Standard boto3 pattern |
| Retry strategy | Client-side retry with exponential backoff | Consistent with existing patterns |

## TransactWriteItems Overview

### What It Provides

DynamoDB TransactWriteItems guarantees ACID properties:
- **Atomicity**: All operations succeed or all fail
- **Consistency**: No partial state visible
- **Isolation**: Concurrent transactions serialize
- **Durability**: Committed transactions persist

### Operation Types

1. **Put**: Insert/replace item (use `ConditionExpression` for insert-only)
2. **Update**: Modify existing item attributes
3. **Delete**: Remove item
4. **ConditionCheck**: Verify condition without modifying (enables read-then-write atomicity)

### Limits

- **Max 100 items** per transaction (we use 4)
- **4MB total size** limit
- **All items in same region**
- **Cross-table supported** (but we use single table)

## Implementation Pattern

### Transaction Structure

```python
from botocore.exceptions import ClientError

def evict_oldest_session_atomic(
    user_id: str,
    oldest_session_pk: str,
    oldest_session_sk: str,
    refresh_token_hash: str,
    new_session_item: dict,
    blocklist_ttl: int
) -> None:
    """
    Atomically evict oldest session, blocklist its token, and create new session.

    Raises:
        SessionLimitRaceError: If transaction fails due to concurrent modification
    """
    table_name = os.environ["USERS_TABLE_NAME"]

    transact_items = [
        # 1. Verify oldest session still exists (prevents double-eviction)
        {
            "ConditionCheck": {
                "TableName": table_name,
                "Key": {
                    "PK": {"S": oldest_session_pk},
                    "SK": {"S": oldest_session_sk}
                },
                "ConditionExpression": "attribute_exists(PK)"
            }
        },
        # 2. Delete the oldest session
        {
            "Delete": {
                "TableName": table_name,
                "Key": {
                    "PK": {"S": oldest_session_pk},
                    "SK": {"S": oldest_session_sk}
                }
            }
        },
        # 3. Add evicted token to blocklist
        {
            "Put": {
                "TableName": table_name,
                "Item": {
                    "PK": {"S": f"BLOCK#refresh#{refresh_token_hash}"},
                    "SK": {"S": "BLOCK"},
                    "ttl": {"N": str(blocklist_ttl)},
                    "evicted_at": {"S": datetime.utcnow().isoformat()},
                    "user_id": {"S": user_id}
                }
            }
        },
        # 4. Create new session (fails if somehow already exists)
        {
            "Put": {
                "TableName": table_name,
                "Item": new_session_item,
                "ConditionExpression": "attribute_not_exists(PK)"
            }
        }
    ]

    try:
        dynamodb = boto3.client("dynamodb")
        dynamodb.transact_write_items(TransactItems=transact_items)
    except ClientError as e:
        if e.response["Error"]["Code"] == "TransactionCanceledException":
            # Check which condition failed
            reasons = e.response.get("CancellationReasons", [])
            raise SessionLimitRaceError(
                "Session eviction race condition - retry login",
                cancellation_reasons=reasons
            )
        raise
```

### Error Handling

```python
class SessionLimitRaceError(Exception):
    """
    Raised when atomic session eviction fails due to concurrent modification.
    Client should retry the login request.
    """
    def __init__(self, message: str, cancellation_reasons: list | None = None):
        super().__init__(message)
        self.cancellation_reasons = cancellation_reasons or []
        self.retryable = True
```

### CancellationReasons Inspection

When transaction fails, `CancellationReasons` array has one entry per operation:

```python
# Example cancellation reasons
[
    {"Code": "ConditionalCheckFailed"},  # ConditionCheck failed - session already evicted
    {"Code": "None"},                     # Delete would have succeeded
    {"Code": "None"},                     # Put blocklist would have succeeded
    {"Code": "None"}                      # Put new session would have succeeded
]
```

## Blocklist Check Pattern

### On Token Refresh

```python
def is_token_blocklisted(refresh_token_hash: str) -> bool:
    """Check if refresh token has been evicted/revoked."""
    table = get_users_table()

    response = table.get_item(
        Key={
            "PK": f"BLOCK#refresh#{refresh_token_hash}",
            "SK": "BLOCK"
        },
        ProjectionExpression="PK"  # Only need existence check
    )

    return "Item" in response
```

### Integration Point

```python
def refresh_session(refresh_token: str) -> TokenResponse:
    token_hash = hash_token(refresh_token)

    # FR-007: Check blocklist BEFORE issuing new tokens
    if is_token_blocklisted(token_hash):
        raise SessionRevokedException("Session has been revoked")

    # ... proceed with token refresh
```

## Alternatives Considered

### Option A: Sequential Conditional Writes (Rejected)

```python
# Problems:
# 1. Not atomic - partial failure possible
# 2. Race window between operations
# 3. Requires manual rollback on failure
table.delete_item(Key=..., ConditionExpression="attribute_exists(PK)")
table.put_item(Item=blocklist_entry)  # What if this fails?
table.put_item(Item=new_session)      # Orphaned blocklist entry
```

### Option B: DynamoDB Streams + Lambda (Rejected)

- **Complexity**: Requires additional Lambda, stream processing
- **Latency**: Eventual consistency, not immediate
- **Cost**: Additional Lambda invocations

### Option C: Single Item with Session Array (Rejected)

- **400KB item limit** could be exceeded
- **Read/write amplification** on every session change
- **No TTL per session** - all-or-nothing expiry

## Performance Considerations

### Transaction Latency

- TransactWriteItems: ~10-20ms typical (same as single write)
- Condition check adds no latency (evaluated server-side)
- Blocklist check: ~5ms (single get_item)

### Cost

- TransactWriteItems: 2x WCU per item (vs 1x for non-transactional)
- For 4 items: 8 WCU total per eviction
- At on-demand pricing: negligible for session management volume

## References

- [AWS TransactWriteItems Documentation](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html)
- [DynamoDB Transactions Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html)
- [Handling TransactionCanceledException](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html#transaction-conflict-handling)
