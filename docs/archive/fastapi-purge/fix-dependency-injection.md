# Fix: Replace Dependency Injection (Depends -> Singletons)

**Parent:** [HL-fastapi-purge-checklist.md](./HL-fastapi-purge-checklist.md)
**Priority:** P5
**Status:** [ ] TODO
**Depends On:** [audit-fastapi-surface.md](./audit-fastapi-surface.md)

---

## Problem Statement

FastAPI's `Depends(get_db)` is a per-request dependency injection system. It creates new instances or runs factory functions on every request. This is the biggest source of "Signature Mismatch" [26.3].

**Replace with:** Static Init Singletons from Round 19, which are created once during the Lambda 10-second init phase and reused across invocations.

---

## Pattern Replacement

### FastAPI Pattern (Current)

```python
from fastapi import Depends

def get_dynamo_client():
    return boto3.resource("dynamodb")

@app.get("/api/v2/tickers/{ticker}/ohlc")
async def get_ohlc(
    ticker: str,
    db = Depends(get_dynamo_client),
):
    table = db.Table(os.environ["OHLC_CACHE_TABLE"])
    ...
```

### Static Singleton Pattern (Target) [19.5]

```python
import boto3
from functools import lru_cache

@lru_cache(maxsize=1)
def get_dynamo_client():
    """Singleton DynamoDB client, created during Lambda init phase."""
    return boto3.resource("dynamodb")

async def handle_ohlc(event: dict, context) -> dict:
    db = get_dynamo_client()  # Free after first call (cached)
    table = db.Table(os.environ["OHLC_CACHE_TABLE"])
    ...
```

---

## Why Singletons Are Better for Lambda

| Aspect | Depends() | Singleton |
|--------|-----------|-----------|
| Init cost | Every request | Once (cold start) |
| Memory | New instance per request | Single instance reused |
| Testability | Mock via `app.dependency_overrides` | Mock via `@patch` or module-level |
| Cold start | Adds latency per-request | Part of 10s init phase (free) |

---

## Migration Checklist

- [ ] Identify all `Depends()` usages from audit
- [ ] For each dependency, determine if it's stateful or stateless
- [ ] Convert stateless factories to `@lru_cache(maxsize=1)` singletons
- [ ] Convert stateful factories to module-level initialization
- [ ] Update handler signatures to remove `Depends()` parameters
- [ ] Call singletons directly inside handler body

---

## Common Dependencies to Convert

| Dependency | Current | Target |
|-----------|---------|--------|
| DynamoDB client | `Depends(get_db)` | `get_dynamo_client()` singleton |
| S3 client | `Depends(get_s3)` | `get_s3_client()` singleton |
| Config/settings | `Depends(get_settings)` | Module-level `SETTINGS` dict |
| Auth/user | `Depends(get_current_user)` | Extract from `event["requestContext"]["authorizer"]` |

---

## Testing Impact

```python
# FastAPI test pattern (current)
app.dependency_overrides[get_db] = lambda: mock_db
client = TestClient(app)

# Native handler test pattern (target)
with patch("src.lambdas.dashboard.ohlc.get_dynamo_client", return_value=mock_db):
    result = lambda_handler(mock_event, mock_context)
```

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/lambdas/dashboard/ohlc.py` | TBD | Remove Depends, call singletons directly |
| `src/lambdas/shared/clients.py` | TBD | May already have singletons; verify |

---

## Related

- [audit-fastapi-surface.md](./audit-fastapi-surface.md) - Lists all Depends() usages
- [fix-test-migration.md](./fix-test-migration.md) - Test mocking changes
