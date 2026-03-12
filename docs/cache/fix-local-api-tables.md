# Fix: Local API DynamoDB Tables

**Parent:** [HL-cache-remediation-checklist.md](./HL-cache-remediation-checklist.md)
**Priority:** P3 (After cache reading fix)
**Status:** [ ] TODO
**Depends On:** [fix-cache-reading.md](./fix-cache-reading.md)

---

## Problem Statement

The local API server (`scripts/run-local-api.py`) creates mock DynamoDB tables for:
- `local-users`
- `local-sentiments`

But it does **NOT** create the OHLC cache table:
- `local-ohlc-cache`

This means cache reads/writes will fail with `ResourceNotFoundException` when testing locally.

---

## Solution: Add OHLC Cache Table

### Implementation

```python
# scripts/run-local-api.py

def create_mock_tables():
    """Create mock DynamoDB tables using moto."""
    import boto3
    from moto import mock_aws

    mock = mock_aws()
    mock.start()

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    # Create users table
    dynamodb.create_table(
        TableName="local-users",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Create sentiments table
    dynamodb.create_table(
        TableName="local-sentiments",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # NEW: Create OHLC cache table
    dynamodb.create_table(
        TableName="local-ohlc-cache",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    logger.info("Created mock DynamoDB tables: local-users, local-sentiments, local-ohlc-cache")
    return mock
```

### Environment Variable

Also need to set the `OHLC_CACHE_TABLE` environment variable:

```python
# scripts/run-local-api.py (near line 75)

os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("USERS_TABLE", "local-users")
os.environ.setdefault("SENTIMENTS_TABLE", "local-sentiments")
os.environ.setdefault("OHLC_CACHE_TABLE", "local-ohlc-cache")  # NEW
```

---

## DynamoDB Table Schema

The OHLC cache table matches production:

| Attribute | Type | Key |
|-----------|------|-----|
| PK | String | Partition Key |
| SK | String | Sort Key |
| open | Number | - |
| high | Number | - |
| low | Number | - |
| close | Number | - |
| volume | Number | - |
| fetched_at | String | - |

### Key Format

- **PK:** `{TICKER}#{source}` (e.g., `AAPL#tiingo`)
- **SK:** `{resolution}#{timestamp}` (e.g., `D#2025-12-23T00:00:00Z`)

---

## Implementation Checklist

### Code Changes

- [ ] Add `local-ohlc-cache` table creation in `create_mock_tables()`
- [ ] Add `OHLC_CACHE_TABLE` environment variable
- [ ] Update log message to list all tables

### Testing

- [ ] Start local API, verify no errors
- [ ] Make OHLC request, verify write-through succeeds
- [ ] Make second request, verify cache read succeeds

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `scripts/run-local-api.py` | 77 | Add `OHLC_CACHE_TABLE` env var |
| `scripts/run-local-api.py` | 100-127 | Add table creation |
| `scripts/run-local-api.py` | 128 | Update log message |

---

## Verification Steps

```bash
# 1. Start local API
python scripts/run-local-api.py

# Expected log:
# "Created mock DynamoDB tables: local-users, local-sentiments, local-ohlc-cache"

# 2. Make OHLC request
curl "http://localhost:8000/api/v2/tickers/AAPL/ohlc?range=1M&resolution=D" \
  -H "Authorization: Bearer test-token"

# 3. Check logs for write-through
# Expected: "OHLC write-through complete"

# 4. Make same request again
curl "http://localhost:8000/api/v2/tickers/AAPL/ohlc?range=1M&resolution=D" \
  -H "Authorization: Bearer test-token"

# 5. Check logs for cache hit
# Expected: "OHLC cache hit (DynamoDB)"
```

---

---

## Future Consideration: Cache Warming (Blind Spot #17)

For production, consider pre-populating cache for popular tickers:

```python
# scripts/warm-ohlc-cache.py (future)
POPULAR_TICKERS = ["AAPL", "MSFT", "GOOG", "AMZN", "TSLA", "META", "NVDA"]

async def warm_cache():
    for ticker in POPULAR_TICKERS:
        for resolution in ["D", "5", "15"]:
            await fetch_and_cache(ticker, resolution, range="1M")
```

**Benefits:**
- First user request is fast (cache hit)
- Reduces Tiingo API calls during peak hours
- Could run on schedule (e.g., 9:00 AM ET before market open)

**Not needed for MVP** - Cache warms naturally on first request.

---

## Related

- [fix-cache-writing.md](./fix-cache-writing.md) - Uses this table for writes
- [fix-cache-reading.md](./fix-cache-reading.md) - Uses this table for reads
- [fix-cache-tests.md](./fix-cache-tests.md) - Tests require this table
