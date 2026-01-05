# Feature 1148: Protect /admin/sessions/revoke Endpoint

## Problem Statement

The `POST /api/v2/admin/sessions/revoke` endpoint allows bulk session revocation (andon cord pattern for security incidents) but is **currently unprotected**. Any authenticated user can revoke any other user's sessions, which is a critical authorization bypass vulnerability (CVSS ~8.0).

## Security Context

- **Phase**: 1.5 (RBAC Infrastructure)
- **Severity**: High - Authorization bypass enabling session hijacking attacks
- **Attack Vector**: Authenticated attacker can:
  1. Revoke legitimate admin sessions
  2. Cause denial-of-service by mass revoking user sessions
  3. Disrupt security incident response by revoking responder sessions

## Requirements

### Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | Endpoint MUST require `operator` role for access |
| FR-002 | Requests without valid JWT MUST return 401 Unauthorized |
| FR-003 | Requests with valid JWT but missing `operator` role MUST return 403 Forbidden |
| FR-004 | Error messages MUST NOT enumerate valid roles (generic messages only) |
| FR-005 | Existing bulk revocation logic MUST remain unchanged |

### Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-001 | Authorization check MUST use existing `@require_role` decorator |
| NFR-002 | No new dependencies may be introduced |
| NFR-003 | Must maintain backward compatibility for authorized callers |

## Technical Design

### Solution: Apply @require_role Decorator

The fix applies the existing `@require_role("operator")` decorator to the endpoint. This decorator:

1. Extracts JWT from Authorization header via `extract_auth_context_typed()`
2. Validates `roles` claim contains required role
3. Returns appropriate error codes (401/403) with generic messages

### Code Change

**File**: `src/lambdas/dashboard/router_v2.py` (lines 548-563)

```python
# Before
@admin_router.post("/sessions/revoke")
async def revoke_sessions_bulk(...):

# After
from src.lambdas.shared.middleware.require_role import require_role

@admin_router.post("/sessions/revoke")
@require_role("operator")
async def revoke_sessions_bulk(request: Request, ...):
```

### Authorization Flow

```
Request → JWT Extraction → Role Validation → Handler
                ↓               ↓
           401 if missing   403 if role missing
```

## Test Plan

### Unit Tests

| Test Case | Expected Outcome |
|-----------|------------------|
| No JWT provided | 401 Unauthorized |
| JWT without roles claim | 403 Forbidden |
| JWT with `free` role only | 403 Forbidden |
| JWT with `paid` role only | 403 Forbidden |
| JWT with `operator` role | 200 OK (handler executes) |
| JWT with expired token | 401 Unauthorized |

### Integration Tests

| Test Case | Expected Outcome |
|-----------|------------------|
| Operator can bulk revoke sessions | Revocation succeeds |
| Non-operator gets 403 on revoke attempt | Access denied |
| Audit trail includes revocation metadata | reason, timestamp logged |

## Dependencies

- Feature 1130: `@require_role` decorator (COMPLETE)
- JWT `roles` claim support (COMPLETE)
- Role constants in `shared/auth/constants.py` (COMPLETE)

## Acceptance Criteria

1. Endpoint protected with `@require_role("operator")`
2. All unit tests pass
3. No regression in authorized bulk revocation functionality
4. Generic error messages (no role enumeration)

## References

- Spec 1130: require_role decorator specification
- SESSION-SUMMARY-2.md: Phase 1.5 RBAC architecture
- Router: `src/lambdas/dashboard/router_v2.py:548-563`
- Decorator: `src/lambdas/shared/middleware/require_role.py`
