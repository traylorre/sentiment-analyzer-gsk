# Research: Require Role Decorator

**Feature**: 1130-require-role-decorator
**Date**: 2026-01-05

## Research Questions

### Q1: Best pattern for FastAPI decorator-based authorization?

**Decision**: Decorator factory wrapping FastAPI dependency injection

**Rationale**:
- FastAPI's `Depends()` is the established pattern in this codebase (see `router_v2.py`)
- A decorator factory provides cleaner syntax: `@require_role('operator')`
- The decorator internally creates a dependency that validates roles
- Compatible with async handlers (all endpoints in codebase are `async def`)

**Pattern**:
```python
def require_role(required_role: str):
    """Decorator factory for role-based access control."""
    if required_role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {required_role}")

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, request: Request, **kwargs):
            # Validate role from auth context
            auth_context = extract_auth_context_typed({"headers": dict(request.headers)})
            if auth_context.user_id is None:
                raise HTTPException(status_code=401, detail="Authentication required")
            if auth_context.roles is None:
                raise HTTPException(status_code=401, detail="Invalid token structure")
            if required_role not in auth_context.roles:
                raise HTTPException(status_code=403, detail="Access denied")
            return await func(*args, request=request, **kwargs)
        return wrapper
    return decorator
```

**Sources**:
- Codebase: `src/lambdas/dashboard/router_v2.py` lines 191-218 (`get_authenticated_user_id`)
- FastAPI docs: Dependency injection pattern

### Q2: How to prevent role enumeration attacks?

**Decision**: Generic error message "Access denied" for all authorization failures

**Rationale**:
- FR-004 explicitly requires preventing role leakage
- Attacker cannot distinguish between:
  - "User has no roles"
  - "User has wrong role"
  - "Role doesn't exist"
  - "Role is disabled"
- Same HTTP 403 status code and identical message body

**Implementation**:
```python
# GOOD: Generic message
raise HTTPException(status_code=403, detail="Access denied")

# BAD: Reveals role information
raise HTTPException(status_code=403, detail="Requires operator role")
raise HTTPException(status_code=403, detail="Missing role: operator")
```

**Sources**:
- OWASP: Authorization Testing Cheat Sheet
- Spec FR-004: "System MUST use a generic 403 error message that does NOT reveal the required role"

### Q3: Where to validate role parameter (startup vs runtime)?

**Decision**: Validate at decoration time (module import/startup)

**Rationale**:
- FR-005 requires startup-time validation
- Typos like `@require_role('admn')` caught immediately on app start
- Prevents silent failures in production
- Uses `VALID_ROLES` constant for validation

**Implementation**:
```python
VALID_ROLES = frozenset({"anonymous", "free", "paid", "operator"})

def require_role(required_role: str):
    if required_role not in VALID_ROLES:
        raise ValueError(f"Invalid role '{required_role}'. Valid roles: {sorted(VALID_ROLES)}")
    # ... rest of decorator
```

**Sources**:
- Python best practices: Fail fast principle
- Spec FR-005: "System MUST validate the role parameter against known canonical roles at decoration time"

### Q4: How to integrate with existing auth context?

**Decision**: Extend `AuthContext` dataclass with `roles: list[str] | None` field

**Rationale**:
- FR-010 requires integration with `extract_auth_context_typed()`
- `AuthContext` already exists with `user_id`, `auth_type`, `auth_method`
- Adding optional `roles` field is backward-compatible
- Roles extracted from JWT `roles` claim during token validation

**Current AuthContext** (from `auth_middleware.py:40-56`):
```python
@dataclass(frozen=True)
class AuthContext:
    user_id: str | None
    auth_type: AuthType
    auth_method: str | None = None
```

**Extended AuthContext**:
```python
@dataclass(frozen=True)
class AuthContext:
    user_id: str | None
    auth_type: AuthType
    auth_method: str | None = None
    roles: list[str] | None = None  # NEW: from JWT 'roles' claim
```

**Sources**:
- Codebase: `src/lambdas/shared/middleware/auth_middleware.py` lines 40-56
- Spec FR-006: "System MUST read user roles from the JWT `roles` claim"

## Alternatives Considered

### Alternative 1: Pure Dependency Function (Rejected)

```python
def check_role(role: str):
    def dependency(request: Request):
        # validation logic
    return dependency

# Usage (verbose)
@router.post("/admin")
async def admin_endpoint(user=Depends(check_role("operator"))):
    ...
```

**Why Rejected**: More verbose syntax, less readable than decorator pattern.

### Alternative 2: Middleware-Based (Rejected)

```python
@app.middleware("http")
async def role_middleware(request: Request, call_next):
    # check role for all requests
```

**Why Rejected**: Too broad - applies to all routes instead of selective protection.

### Alternative 3: Database Role Lookup (Rejected)

```python
async def get_user_roles(user_id: str) -> list[str]:
    # Query DynamoDB for user roles
```

**Why Rejected**:
- Adds latency (DynamoDB call per request)
- Violates assumption that roles are in JWT
- Not consistent with Phase 1.5 JWT-based role design

## Key Findings Summary

| Topic | Decision | Key Benefit |
|-------|----------|-------------|
| Pattern | Decorator factory + dependency injection | Clean syntax, FastAPI-native |
| Error messages | Generic "Access denied" | Prevents enumeration |
| Validation timing | Decoration time (startup) | Fail fast, no runtime surprises |
| Auth integration | Extend AuthContext | Backward compatible, reuses existing parsing |
| Role storage | JWT claims | No database lookup, consistent with Phase 1.5 |
