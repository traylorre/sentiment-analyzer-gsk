# Feature 1149: Protect /users/lookup Endpoint

## Problem Statement

The `GET /api/v2/users/lookup` endpoint allows looking up users by email address but is **currently unprotected**. Any request can query whether an email exists in the system, enabling account enumeration attacks (CVSS ~5.3 information disclosure).

## Security Context

- **Phase**: 1.5 (RBAC Infrastructure)
- **Severity**: Medium - Information disclosure enabling account enumeration
- **Attack Vector**: Attacker can:
  1. Harvest valid email addresses from the system
  2. Build target lists for phishing/credential stuffing attacks
  3. Determine user existence for social engineering

## Requirements

### Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | Endpoint MUST require `operator` role for access |
| FR-002 | Requests without valid JWT MUST return 401 Unauthorized |
| FR-003 | Requests with valid JWT but missing `operator` role MUST return 403 Forbidden |
| FR-004 | Error messages MUST NOT enumerate valid roles (generic messages only) |
| FR-005 | Existing lookup logic MUST remain unchanged |

### Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-001 | Authorization check MUST use existing `@require_role` decorator |
| NFR-002 | No new dependencies may be introduced |
| NFR-003 | Must maintain backward compatibility for authorized callers |

## Technical Design

### Solution: Apply @require_role Decorator

The fix applies the existing `@require_role("operator")` decorator to the endpoint.

### Code Change

**File**: `src/lambdas/dashboard/router_v2.py` (lines 704-736)

```python
# Before
@users_router.get("/lookup")
async def lookup_user_by_email(...):

# After
from src.lambdas.shared.middleware.require_role import require_role

@users_router.get("/lookup")
@require_role("operator")
async def lookup_user_by_email(request: Request, ...):
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

## Dependencies

- Feature 1130: `@require_role` decorator (COMPLETE)
- JWT `roles` claim support (COMPLETE)

## Acceptance Criteria

1. Endpoint protected with `@require_role("operator")`
2. All unit tests pass
3. No regression in lookup functionality
4. Generic error messages (no role enumeration)

## References

- Similar to Feature 1148: Protect /admin/sessions/revoke
- Decorator: `src/lambdas/shared/middleware/require_role.py`
