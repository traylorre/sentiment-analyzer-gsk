# Data Model: Require Role Decorator

**Feature**: 1130-require-role-decorator
**Date**: 2026-01-05

## Entities

### 1. Role (Canonical Values)

**Location**: `src/lambdas/shared/auth/constants.py`

| Value | Description | Typical Assignment |
|-------|-------------|-------------------|
| `anonymous` | Unauthenticated user with UUID token | Auto-assigned to anonymous sessions |
| `free` | Authenticated user, no subscription | Default for email/OAuth sign-up |
| `paid` | Active subscription holder | When `subscription_active=True` |
| `operator` | Administrative access | Manual assignment by existing operator |

**Constraints**:
- Roles are additive: a `paid` user has `['free', 'paid']`
- An `operator` user has `['free', 'paid', 'operator']` or `['free', 'operator']` depending on subscription
- `anonymous` users have `['anonymous']` only
- Empty roles list `[]` is treated as unauthorized for any role check

**Implementation**:
```python
from enum import StrEnum

class Role(StrEnum):
    ANONYMOUS = "anonymous"
    FREE = "free"
    PAID = "paid"
    OPERATOR = "operator"

VALID_ROLES: frozenset[str] = frozenset(role.value for role in Role)
```

### 2. AuthContext (Extended)

**Location**: `src/lambdas/shared/middleware/auth_middleware.py`

**Current Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `str \| None` | User UUID or None if no auth |
| `auth_type` | `AuthType` | `ANONYMOUS` or `AUTHENTICATED` |
| `auth_method` | `str \| None` | `"bearer"`, `"x-user-id"`, or None |

**New Field**:
| Field | Type | Description |
|-------|------|-------------|
| `roles` | `list[str] \| None` | List of role strings from JWT `roles` claim |

**Extended Definition**:
```python
@dataclass(frozen=True)
class AuthContext:
    """Authentication context from validated token (Feature 1048)."""
    user_id: str | None
    auth_type: AuthType
    auth_method: str | None = None
    roles: list[str] | None = None  # Feature 1130: Role-based access control
```

**Invariants**:
- If `user_id is None`, then `roles` should be `None` (no auth = no roles)
- If `auth_type == ANONYMOUS`, then `roles` should be `["anonymous"]`
- If `auth_type == AUTHENTICATED`, then `roles` should be non-empty list

### 3. RoleValidationError (Internal Exception)

**Location**: `src/lambdas/shared/errors/auth_errors.py`

| Exception | Description | HTTP Mapping |
|-----------|-------------|--------------|
| `InvalidRoleError` | Role parameter not in VALID_ROLES | N/A (startup error) |
| `MissingRolesClaimError` | JWT has no `roles` claim | 401 Unauthorized |
| `InsufficientRoleError` | User lacks required role | 403 Forbidden |

**Implementation**:
```python
class InvalidRoleError(ValueError):
    """Raised at decoration time for invalid role parameters."""
    def __init__(self, role: str, valid_roles: frozenset[str]):
        self.role = role
        self.valid_roles = valid_roles
        super().__init__(f"Invalid role '{role}'. Valid roles: {sorted(valid_roles)}")

class MissingRolesClaimError(Exception):
    """Raised when JWT is missing the roles claim."""
    pass

class InsufficientRoleError(Exception):
    """Raised when user lacks the required role."""
    pass
```

## State Transitions

### Role Assignment Flow

```
User Creation → Anonymous Session
    roles: ["anonymous"]
        ↓
Email/OAuth Sign-up → Free User
    roles: ["free"]
        ↓
Subscription Purchase → Paid User
    roles: ["free", "paid"]
        ↓
Operator Assignment → Operator
    roles: ["free", "paid", "operator"] or ["free", "operator"]
```

### Role Check Flow

```
Request Received
    ↓
Extract Auth Context (extract_auth_context_typed)
    ↓
Check user_id present?
    ├── No → 401 "Authentication required"
    └── Yes ↓
Check roles claim present?
    ├── No → 401 "Invalid token structure"
    └── Yes ↓
Check required_role in roles?
    ├── No → 403 "Access denied"
    └── Yes → Proceed to handler
```

## Relationships

```
┌─────────────────┐
│   JWT Token     │
│  ┌───────────┐  │
│  │  roles    │──┼──→ AuthContext.roles
│  │  claim    │  │
│  └───────────┘  │
└─────────────────┘
        ↓
┌─────────────────┐
│  AuthContext    │
│  ┌───────────┐  │
│  │ user_id   │  │
│  │ auth_type │  │
│  │ auth_meth │  │
│  │ roles     │──┼──→ @require_role validation
│  └───────────┘  │
└─────────────────┘
        ↓
┌─────────────────┐
│ @require_role   │
│  ┌───────────┐  │
│  │ required  │──┼──→ Check: required_role in roles
│  │ role      │  │
│  └───────────┘  │
└─────────────────┘
```

## Validation Rules

| Rule | Enforcement | Error |
|------|-------------|-------|
| Role parameter must be valid | Decoration time | `InvalidRoleError` |
| User must be authenticated | Request time | HTTP 401 |
| JWT must have roles claim | Request time | HTTP 401 |
| User must have required role | Request time | HTTP 403 |
| Error messages must be generic | Code review | N/A |
