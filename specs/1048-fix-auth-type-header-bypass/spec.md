# Feature 1048: Fix X-Auth-Type Header Bypass Vulnerability

## Problem Statement

The `get_authenticated_user_id()` function in `router_v2.py:187-198` reads the `X-Auth-Type` header directly from the request to determine if a user is anonymous or authenticated. This header is **client-provided** and not validated by the auth middleware.

**Security Impact**: Anonymous users can bypass "authenticated only" endpoint restrictions by sending `X-Auth-Type: authenticated` header with their anonymous session token.

**Affected Endpoints**:
- `POST /api/v2/alerts` (line 1365)
- `GET /api/v2/alerts` (line 1385)
- `POST /api/v2/configurations/{config_id}/alerts` (line 1044)
- `PATCH /api/v2/configurations/{config_id}/alerts/{alert_id}` (line 1082)
- `DELETE /api/v2/configurations/{config_id}/alerts/{alert_id}` (line 1112)
- All `/api/v2/notifications/*` endpoints (lines 1516, 1534, etc.)
- All `/chaos/experiments/*` endpoints (lines 804, 861, 895, etc.)

## Root Cause Analysis

1. `auth_middleware.py:extract_user_id()` correctly extracts user_id from:
   - Bearer token (UUID = anonymous, JWT = authenticated)
   - X-User-ID header (UUID only = anonymous)

2. But `extract_user_id()` only returns the user_id string - it does NOT indicate whether the token was a JWT (authenticated) or UUID (anonymous).

3. `router_v2.py:get_authenticated_user_id()` then trusts the client-provided `X-Auth-Type` header to determine authentication status.

## Solution Design

### Approach: Return Auth Context from Middleware

Modify `extract_user_id()` to return an `AuthContext` dataclass that includes both the user_id AND the auth_type (determined by token validation, not client headers).

### Data Model

```python
from dataclasses import dataclass
from enum import Enum

class AuthType(str, Enum):
    """Authentication type determined by token validation."""
    ANONYMOUS = "anonymous"      # UUID token (no JWT claims)
    AUTHENTICATED = "authenticated"  # JWT with valid claims
    UNAUTHENTICATED = "unauthenticated"  # No valid token

@dataclass
class AuthContext:
    """Authentication context from validated token."""
    user_id: str | None
    auth_type: AuthType
    token_type: str | None = None  # "bearer_uuid", "bearer_jwt", "x-user-id"
```

### Changes Required

1. **auth_middleware.py**:
   - Add `AuthContext` and `AuthType` definitions
   - Create `extract_auth_context()` that returns `AuthContext` (not just user_id)
   - Keep `extract_user_id()` for backward compatibility (delegates to new function)

2. **router_v2.py**:
   - Import `AuthContext`, `AuthType` from middleware
   - Modify `get_user_id_from_request()` to use `extract_auth_context()`
   - Modify `get_authenticated_user_id()` to check `auth_context.auth_type` instead of header
   - Remove trust in `request.headers.get("X-Auth-Type")`

3. **Tests**:
   - Add unit test: anonymous user with `X-Auth-Type: authenticated` header → 403
   - Add unit test: JWT user without header → 200 (auth_type from token)
   - Add integration test for affected endpoints

## Acceptance Criteria

- [ ] AC1: Anonymous session with `X-Auth-Type: authenticated` header returns 403 on alerts endpoint
- [ ] AC2: JWT session without `X-Auth-Type` header succeeds on alerts endpoint
- [ ] AC3: Auth type determined by token validation, not request headers
- [ ] AC4: Backward compatibility maintained for existing endpoints
- [ ] AC5: All existing tests pass

## Out of Scope

- SSE query param token handling (Feature 1049)
- Direct header access in ohlc.py (Feature 1049)
- Removing deprecated `INTERNAL_API_KEY` references

## Files to Modify

| File | Changes |
|------|---------|
| `src/lambdas/shared/middleware/auth_middleware.py` | Add AuthContext, AuthType, extract_auth_context() |
| `src/lambdas/dashboard/router_v2.py` | Use AuthContext.auth_type instead of X-Auth-Type header |
| `tests/unit/shared/middleware/test_auth_middleware.py` | Add AuthContext tests |
| `tests/unit/dashboard/test_router_v2.py` | Add bypass attempt tests |

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing clients that rely on X-Auth-Type | None expected - this was never part of API contract, only internal abuse vector |
| Changing auth_middleware return type | Maintain backward-compatible extract_user_id() function |
| Missing edge cases in auth type detection | Comprehensive test coverage including edge cases |

## Context

Discovered during Feature 1047/1039 review. Part of auth consistency initiative: ONE URL = ONE auth method.
