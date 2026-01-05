# Quickstart: Protect Admin Sessions Revoke Endpoint

**Feature**: 001-protect-admin-sessions
**Date**: 2026-01-05

## Implementation Steps

### Step 1: Add Import

In `src/lambdas/dashboard/router_v2.py`, add the import:

```python
from src.lambdas.shared.middleware.require_role import require_role
```

### Step 2: Apply Decorator

Add the decorator to the `revoke_sessions_bulk` endpoint (around line 548):

```python
@admin_router.post("/sessions/revoke")
@require_role("operator")
async def revoke_sessions_bulk(
    body: BulkRevocationRequest,
    table=Depends(get_users_table),
):
    # Existing implementation unchanged
    ...
```

**Note**: The decorator order matters - `@require_role` should be after the route decorator.

### Step 3: Add Unit Tests

Create tests in `tests/unit/dashboard/test_router_v2_auth.py`:

1. Test that operator user (roles=["operator"]) gets 200
2. Test that non-operator user (roles=["free"]) gets 403
3. Test that unauthenticated request gets 401

## Verification

```bash
# Run unit tests
pytest tests/unit/dashboard/ -k revoke -v

# Run all auth tests
pytest tests/unit/dashboard/ -v
```

## Dependencies

- `@require_role` decorator from Feature 1130 (existing)
- No new packages required

## Valid Roles

From `src/lambdas/shared/auth/constants.py`:
- `anonymous` - UUID token holders
- `free` - Authenticated users
- `paid` - Subscription holders
- `operator` - Administrative access

## Common Issues

1. **Import path wrong**: The decorator is at `src/lambdas/shared/middleware/require_role.py`
2. **Decorator order**: Route decorator must come first, then `@require_role`
3. **Missing roles claim**: Ensure JWT tokens include `roles` claim for testing
4. **Wrong role name**: Use `"operator"` not `"admin"` - see constants.py
