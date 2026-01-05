# Research: Protect Admin Sessions Revoke Endpoint

**Feature**: 001-protect-admin-sessions
**Date**: 2026-01-05
**Status**: Complete

## Research Questions

### Q1: How to use the @require_role decorator from Feature 1130?

**Decision**: Import and apply `@require_role("operator")` before the endpoint handler

**Rationale**: Feature 1130 implemented the `@require_role` decorator which:
1. Checks the JWT `roles` claim for the required role
2. Returns 403 Forbidden if role is not present
3. Requires authentication first (401 if not authenticated)

**Note**: The system uses `"operator"` role (not `"admin"`) as defined in `src/lambdas/shared/auth/constants.py`.
Valid roles: anonymous, free, paid, operator.

**Implementation**:
```python
from src.lambdas.shared.middleware.require_role import require_role

@admin_router.post("/sessions/revoke")
@require_role("operator")
async def revoke_sessions_bulk(body: BulkRevocationRequest, table=Depends(get_users_table)):
    # Existing implementation
    ...
```

**Alternatives Considered**:
- Manual role check in handler: Rejected - duplicates decorator logic
- New decorator: Rejected - Feature 1130 decorator already exists

---

### Q2: Where is the revoke endpoint located?

**Decision**: The endpoint is in `src/lambdas/dashboard/router_v2.py`

**Location Details**:
- File: `src/lambdas/dashboard/router_v2.py`
- Endpoint: `POST /api/v2/admin/sessions/revoke`
- Handler function: `revoke_sessions_bulk` (line 548-563)
- Router: `admin_router` with prefix `/api/v2/admin`

---

## Summary of Changes

| Component | Change |
|-----------|--------|
| `router_v2.py` | Add `@require_role("operator")` decorator to revoke_sessions_bulk |
| Unit tests | Add tests for 403 when non-operator, 200 when operator |

## Dependencies

- `@require_role` decorator from Feature 1130 (existing)
- No new dependencies required

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing operator access | Test that operator role continues to work |
| Decorator import path | Verified: `from src.lambdas.shared.middleware.require_role import require_role` |
