# Implementation Tasks: Feature 1154 - SSE Lambda Bearer Token Authentication

**Feature Branch**: `1154-sse-bearer-token-auth`
**Spec**: [spec.md](./spec.md)
**Created**: 2026-01-06

## Overview

The SSE Lambda handler at `/src/lambdas/sse_streaming/handler.py` does not check the `Authorization: Bearer` header. It only supports X-User-ID header and user_token query parameter. This blocks E2E tests that use Bearer token authentication (per Feature 1146).

## File Changes

**Primary File**:
- `src/lambdas/sse_streaming/handler.py` - Add Bearer token extraction and validation

**Test Files**:
- `tests/unit/lambdas/sse_streaming/test_handler_auth.py` - Unit tests for new auth logic

## Implementation Tasks

### T1: Add Authorization Header Parameter to config_stream

**File**: `src/lambdas/sse_streaming/handler.py`
**Lines**: ~346-355 (function signature)

Add `authorization` header parameter to the function signature:

```python
async def config_stream(
    request: Request,
    config_id: str,
    authorization: str | None = Header(None, alias="Authorization"),  # NEW
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    user_token: str | None = Query(None, description="User token for EventSource auth"),
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
):
```

**Acceptance**: Function accepts Authorization header parameter.

---

### T2: Add Bearer Token Extraction Logic

**File**: `src/lambdas/sse_streaming/handler.py`
**Lines**: ~390-410 (authentication logic section)

Add Bearer token extraction BEFORE existing X-User-ID check. The precedence is:
1. Bearer token (highest priority)
2. X-User-ID header
3. user_token query parameter (lowest priority)

```python
# T034: Validate authentication - Bearer token > header > query param
user_id = None
auth_method = None

# NEW: Check Authorization: Bearer header first (Feature 1154)
if authorization and authorization.startswith("Bearer "):
    bearer_token = authorization[7:].strip()
    if bearer_token:
        user_id = bearer_token
        auth_method = "bearer"

# Existing: X-User-ID header fallback
if not user_id and x_user_id and x_user_id.strip():
    user_id = x_user_id.strip()
    auth_method = "header"

# Existing: Query param fallback
elif not user_id and user_token and user_token.strip():
    user_id = user_token.strip()
    auth_method = "query_param"
```

**Acceptance**: Bearer token is extracted and takes precedence over other auth methods.

---

### T3: Add JWT Validation for Bearer Tokens (Optional Enhancement)

**Note**: This task is OPTIONAL for MVP. The current E2E tests use UUID tokens, not JWTs. Full JWT validation can be added later if needed.

If JWT validation is required, import shared auth:

```python
from src.lambdas.shared.middleware.auth_middleware import validate_jwt, JWTConfig

# In auth logic:
if authorization and authorization.startswith("Bearer "):
    bearer_token = authorization[7:].strip()
    if bearer_token:
        # Try JWT validation first
        jwt_claim = validate_jwt(bearer_token)
        if jwt_claim:
            user_id = jwt_claim.sub  # Extract user_id from JWT sub claim
            auth_method = "jwt"
        else:
            # Fallback: treat as raw UUID token (anonymous session)
            user_id = bearer_token
            auth_method = "bearer_uuid"
```

**Acceptance**: JWT tokens are validated; UUID tokens pass through.

---

### T4: Update Error Message to Include Bearer Option

**File**: `src/lambdas/sse_streaming/handler.py`
**Lines**: ~405-415 (error response)

Update the 401 error message to mention Bearer token support:

```python
if not user_id:
    logger.warning(
        "Config stream rejected - missing authentication",
        extra={"config_id": sanitize_for_log(config_id[:8] if config_id else "")},
    )
    return JSONResponse(
        status_code=401,
        content={
            "detail": "Authentication required. Provide Authorization: Bearer header, X-User-ID header, or user_token query parameter."
        },
    )
```

**Acceptance**: Error message lists all three auth options.

---

### T5: Add Unit Tests for Bearer Token Auth

**File**: `tests/unit/lambdas/sse_streaming/test_handler_auth.py` (NEW)

Create unit tests covering:

1. `test_bearer_token_auth_success` - Valid Bearer token authenticates
2. `test_bearer_token_precedence_over_x_user_id` - Bearer takes precedence
3. `test_x_user_id_fallback_when_no_bearer` - Backwards compatibility
4. `test_query_param_fallback` - user_token still works
5. `test_missing_auth_returns_401` - No auth returns 401
6. `test_invalid_bearer_format_falls_back` - "Bearer" without token falls back

**Acceptance**: All unit tests pass.

---

### T6: Verify E2E Tests Pass

Run the E2E tests that were failing:

```bash
pytest tests/e2e/test_sse.py -v
```

Expected passing tests:
- `test_sse_connection_established`
- `test_sse_receives_sentiment_update`
- `test_sse_receives_refresh_event`
- `test_sse_reconnection_with_last_event_id`

**Acceptance**: All 4 SSE E2E tests pass.

---

## Verification Checklist

- [ ] T1: Authorization header parameter added
- [ ] T2: Bearer token extraction logic added
- [ ] T3: (Optional) JWT validation integrated
- [ ] T4: Error message updated
- [ ] T5: Unit tests added and passing
- [ ] T6: E2E tests passing

## Dependencies

- JWT_SECRET environment variable is deployed (confirmed)
- Shared auth modules available at `src/lambdas/shared/middleware/auth_middleware.py`

## Risks

- **Low**: Breaking change if clients send malformed Bearer tokens (mitigated by fallback)
- **Low**: JWT validation overhead (mitigated by making it optional for MVP)
