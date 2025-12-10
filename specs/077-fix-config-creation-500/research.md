# Research: Fix Config Creation 500 Error

**Feature**: 077-fix-config-creation-500
**Date**: 2025-12-10

## Summary

The configuration creation endpoint (`POST /api/v2/configurations`) returns HTTP 500 in the preprod environment, despite all unit tests passing locally. This is an environment/integration issue, not a code logic error.

## Investigation Findings

### 1. Unit Tests Status: PASS

All 16 configuration-related unit tests pass:
- `test_creates_configuration_with_valid_request`
- `test_returns_error_for_max_configurations`
- `test_returns_error_for_invalid_ticker`
- `test_creates_valid_uuid_for_config_id`
- `test_stores_correct_dynamodb_keys`
- Plus list, get, update, delete tests

### 2. Code Analysis

**Endpoint Handler** (`router_v2.py:681-700`):
```python
@config_router.post("")
async def create_configuration(
    request: Request,
    body: config_service.ConfigurationCreate,
    table=Depends(get_dynamodb_table),
    ticker_cache: TickerCache | None = Depends(get_ticker_cache_dependency),
):
    user_id = get_user_id_from_request(request)
    result = config_service.create_configuration(...)
```

**Service Function** (`configurations.py:199-282`):
1. Counts user configs (max 2 check)
2. Validates tickers via `_validate_ticker()`
3. Creates Configuration model
4. Calls `table.put_item()` to persist
5. Invalidates cache
6. Returns `ConfigurationResponse`

**Potential Failure Points**:
1. `get_user_id_from_request()` - Could fail if token validation issues
2. `_validate_ticker()` - Depends on `ticker_cache` from S3
3. `table.put_item()` - DynamoDB write operation
4. Any unhandled exception bubbles up as 500

### 3. Environment Dependencies

| Component | Config Source | Risk |
|-----------|---------------|------|
| DynamoDB Table | `DYNAMODB_TABLE` env var | Missing table or permissions |
| Ticker Cache | `TICKER_CACHE_BUCKET` env var | S3 access or missing file |
| Session Validation | Bearer token | Token validation failure |

### 4. CloudWatch Logs Analysis

Recent errors from preprod Lambda show errors in:
- `refresh_access_tokens` (Cognito-related)
- `cognito_refresh_tokens`

No specific config creation errors captured in last 24 hours - indicates the E2E tests are skipping before making requests, or errors aren't being logged properly.

### 5. E2E Test Skip Pattern

Tests skip when they receive 500:
```python
if response.status_code == 500:
    pytest.skip("Config creation endpoint returning 500 - API issue")
```

This prevents cascade failures but masks root cause.

## Root Cause Hypotheses

### Hypothesis A: Ticker Cache S3 Access (HIGH PROBABILITY)

**Evidence**:
- `get_ticker_cache_dependency()` catches exceptions and returns `None`
- When `ticker_cache=None`, `_validate_ticker()` accepts any ticker without validation
- But if S3 access fails with an uncaught exception in `TickerCache.load_from_s3()`, it could surface as 500

**Test**: Check `TICKER_CACHE_BUCKET` env var and S3 permissions

### Hypothesis B: DynamoDB Permissions (MEDIUM PROBABILITY)

**Evidence**:
- `table.put_item()` exception is caught and re-raised
- Lambda IAM role may lack `dynamodb:PutItem` permission
- Or table schema mismatch

**Test**: Check Lambda IAM role permissions and table existence

### Hypothesis C: Session/Token Validation (LOW PROBABILITY)

**Evidence**:
- `get_user_id_from_request()` may throw if token is invalid
- But E2E tests create fresh tokens before config creation

**Test**: Check if anonymous session tokens work correctly

## Log Injection Prevention (FR-006)

**Decision**: Never log user-generated content (ticker symbols, config names, request payloads)
**Rationale**: Prevents CWE-117 log injection vulnerabilities and CodeQL warnings
**Alternatives Considered**:
- Sanitizing user input before logging - Rejected: Too easy to miss edge cases
- Only logging hashes of user content - Acceptable for correlation IDs

**Safe Logging Pattern**:
```python
# SAFE: Log counts and system values
logger.info("Config creation", extra={
    "ticker_count": len(tickers),
    "user_id_hash": sha256(user_id)[:12],
    "operation": "create_configuration"
})

# UNSAFE: Never log user content directly
# logger.info(f"Creating config with tickers: {tickers}")  # CWE-117!
```

## Decision

**Approach**: Debug-first implementation with CodeQL-safe logging

1. Add detailed error logging to identify exact failure point (safe fields only)
2. Test S3 ticker cache access
3. Verify DynamoDB permissions and table schema
4. Add proper exception handling to return 4xx instead of 500 where appropriate

## Alternatives Considered

| Alternative | Rejected Because |
|-------------|-----------------|
| Skip ticker validation entirely | Would allow invalid tickers, degrading data quality |
| Hardcode ticker list | Not maintainable, misses delisted stocks |
| Return 503 for all errors | Doesn't help debugging |
| Log full request for debugging | Violates FR-006, causes CodeQL CWE-117 warnings |

## Implementation Approach

1. **Phase 1: Diagnostics**
   - Add structured logging at each failure point (no user content)
   - Deploy to preprod and capture logs
   - Identify exact exception type and stack trace

2. **Phase 2: Fix Root Cause**
   - Based on diagnostics, fix the underlying issue
   - Add defensive error handling for graceful degradation

3. **Phase 3: Verification**
   - Remove E2E test skips
   - Run full E2E suite
   - Verify 8+ dependent tests pass
   - Confirm CodeQL analysis passes with 0 new CWE-117 findings
