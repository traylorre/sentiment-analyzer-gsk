# Feature 1048: Implementation Plan

## Phase 1: Add AuthContext to Middleware

### Task 1.1: Define AuthType enum and AuthContext dataclass

**File**: `src/lambdas/shared/middleware/auth_middleware.py`

Add after line 38 (after JWTClaim):

```python
from enum import Enum

class AuthType(str, Enum):
    """Authentication type determined by token validation."""
    ANONYMOUS = "anonymous"      # UUID token (no JWT claims)
    AUTHENTICATED = "authenticated"  # JWT with valid claims

@dataclass(frozen=True)
class AuthContext:
    """Authentication context from validated token.

    Attributes:
        user_id: Validated user ID (or None if unauthenticated)
        auth_type: ANONYMOUS for UUID tokens, AUTHENTICATED for JWT
        token_source: Where the token came from ("bearer", "x-user-id")
    """
    user_id: str | None
    auth_type: AuthType
    token_source: str | None = None
```

### Task 1.2: Create extract_auth_context() function

**File**: `src/lambdas/shared/middleware/auth_middleware.py`

Add new function (after `extract_user_id`):

```python
def extract_auth_context(event: dict[str, Any]) -> AuthContext:
    """Extract authentication context from request.

    Determines auth_type based on token validation:
    - JWT token with valid claims → AUTHENTICATED
    - UUID token (no JWT) → ANONYMOUS
    - No valid token → ANONYMOUS with user_id=None

    Args:
        event: Lambda event dict with headers

    Returns:
        AuthContext with validated user_id and auth_type
    """
    headers = event.get("headers", {}) or {}
    normalized_headers = {k.lower(): v for k, v in headers.items()}

    # Try Bearer token first (preferred)
    auth_header = normalized_headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

        # Check if it's a JWT first (authenticated)
        jwt_claim = validate_jwt(token)
        if jwt_claim:
            return AuthContext(
                user_id=jwt_claim.subject,
                auth_type=AuthType.AUTHENTICATED,
                token_source="bearer"
            )

        # Fall back to UUID token (anonymous)
        if _is_valid_uuid(token):
            return AuthContext(
                user_id=token,
                auth_type=AuthType.ANONYMOUS,
                token_source="bearer"
            )

    # Try X-User-ID header (legacy, always anonymous)
    user_id = normalized_headers.get("x-user-id")
    if user_id and _is_valid_uuid(user_id):
        return AuthContext(
            user_id=user_id,
            auth_type=AuthType.ANONYMOUS,
            token_source="x-user-id"
        )

    # No valid auth
    return AuthContext(
        user_id=None,
        auth_type=AuthType.ANONYMOUS,
        token_source=None
    )
```

### Task 1.3: Update module exports

**File**: `src/lambdas/shared/middleware/auth_middleware.py`

Ensure `AuthType`, `AuthContext`, and `extract_auth_context` are importable.

## Phase 2: Update router_v2.py

### Task 2.1: Import new types

**File**: `src/lambdas/dashboard/router_v2.py`

Update imports:

```python
from src.lambdas.shared.middleware.auth_middleware import (
    extract_user_id,  # Keep for backward compat
    extract_auth_context,  # New
    AuthContext,  # New
    AuthType,  # New
)
```

### Task 2.2: Modify get_authenticated_user_id()

**File**: `src/lambdas/dashboard/router_v2.py` (lines 187-198)

**Before**:
```python
def get_authenticated_user_id(request: Request) -> str:
    user_id = get_user_id_from_request(request)
    auth_type = request.headers.get("X-Auth-Type", "anonymous")  # VULNERABLE
    if auth_type == "anonymous":
        raise HTTPException(
            status_code=403, detail="This endpoint requires authenticated user"
        )
    return user_id
```

**After**:
```python
def get_authenticated_user_id(request: Request) -> str:
    """Get authenticated user ID (non-anonymous).

    For endpoints that require authenticated users (not anonymous).
    Auth type is determined by token validation, NOT request headers.
    """
    # Build event dict for auth context extraction
    event = {"headers": dict(request.headers)}
    auth_context = extract_auth_context(event)

    if auth_context.user_id is None:
        raise HTTPException(
            status_code=401, detail="Authentication required"
        )

    if auth_context.auth_type == AuthType.ANONYMOUS:
        raise HTTPException(
            status_code=403, detail="This endpoint requires authenticated user"
        )

    return auth_context.user_id
```

## Phase 3: Add Tests

### Task 3.1: Unit tests for AuthContext

**File**: `tests/unit/shared/middleware/test_auth_middleware.py`

```python
class TestAuthContext:
    """Tests for extract_auth_context function."""

    def test_jwt_token_returns_authenticated(self):
        """JWT token should return AUTHENTICATED auth_type."""
        # Create valid JWT
        token = create_test_jwt(user_id="user-123")
        event = {"headers": {"Authorization": f"Bearer {token}"}}

        context = extract_auth_context(event)

        assert context.user_id == "user-123"
        assert context.auth_type == AuthType.AUTHENTICATED
        assert context.token_source == "bearer"

    def test_uuid_bearer_returns_anonymous(self):
        """UUID Bearer token should return ANONYMOUS auth_type."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"Authorization": f"Bearer {user_id}"}}

        context = extract_auth_context(event)

        assert context.user_id == user_id
        assert context.auth_type == AuthType.ANONYMOUS
        assert context.token_source == "bearer"

    def test_x_user_id_returns_anonymous(self):
        """X-User-ID header should return ANONYMOUS auth_type."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"X-User-ID": user_id}}

        context = extract_auth_context(event)

        assert context.user_id == user_id
        assert context.auth_type == AuthType.ANONYMOUS
        assert context.token_source == "x-user-id"

    def test_no_auth_returns_none_user_id(self):
        """No auth headers should return None user_id."""
        event = {"headers": {}}

        context = extract_auth_context(event)

        assert context.user_id is None
        assert context.auth_type == AuthType.ANONYMOUS
```

### Task 3.2: Bypass attempt tests

**File**: `tests/unit/dashboard/test_router_v2.py`

```python
class TestAuthBypassPrevention:
    """Tests to verify X-Auth-Type header bypass is prevented."""

    def test_anonymous_with_auth_type_header_rejected(self, client, mock_table):
        """Anonymous user sending X-Auth-Type: authenticated should be rejected."""
        user_id = str(uuid.uuid4())  # Anonymous UUID

        response = client.post(
            "/api/v2/alerts",
            headers={
                "X-User-ID": user_id,
                "X-Auth-Type": "authenticated"  # Bypass attempt
            },
            json={"name": "Test Alert", "condition": {...}}
        )

        assert response.status_code == 403
        assert "authenticated user" in response.json()["detail"]

    def test_jwt_user_without_header_accepted(self, client, mock_table):
        """JWT user without X-Auth-Type header should be accepted."""
        token = create_test_jwt(user_id="user-123")

        response = client.get(
            "/api/v2/alerts",
            headers={"Authorization": f"Bearer {token}"}
            # No X-Auth-Type header - auth determined from token
        )

        assert response.status_code in (200, 404)  # 404 if no alerts, 200 otherwise
```

## Phase 4: Verification

### Task 4.1: Run existing tests
```bash
pytest tests/unit/shared/middleware/test_auth_middleware.py -v
pytest tests/unit/dashboard/test_router_v2.py -v
```

### Task 4.2: Run full test suite
```bash
pytest tests/unit/ -v --tb=short
```

## Dependency Graph

```
Task 1.1 (AuthType, AuthContext)
    ↓
Task 1.2 (extract_auth_context)
    ↓
Task 1.3 (exports)
    ↓
Task 2.1 (imports in router_v2)
    ↓
Task 2.2 (fix get_authenticated_user_id)
    ↓
Task 3.1 + 3.2 (tests - can run in parallel)
    ↓
Task 4.1 + 4.2 (verification)
```

## Rollback Plan

If issues discovered:
1. Revert `get_authenticated_user_id()` to use header (temporary)
2. Keep `AuthContext` infrastructure for future use
3. File follow-up issue for root cause

## Success Criteria

- [ ] All existing tests pass
- [ ] New bypass prevention tests pass
- [ ] Anonymous user with `X-Auth-Type: authenticated` → 403
- [ ] JWT user without `X-Auth-Type` header → 200 (or appropriate response)
