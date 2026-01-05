# Tasks: Feature 1148

## Task Execution Order

### T001: Add require_role Import
- [ ] Add import statement to router_v2.py
- **File**: `src/lambdas/dashboard/router_v2.py`
- **Change**: `from src.lambdas.shared.middleware.require_role import require_role`

### T002: Apply Decorator to Endpoint
- [ ] Add `@require_role("operator")` decorator
- **File**: `src/lambdas/dashboard/router_v2.py`
- **Location**: After `@admin_router.post("/sessions/revoke")`, before function def
- **Important**: Decorator order: route decorator first, then require_role

### T003: Add Request Parameter
- [ ] Add `request: Request` as first parameter to handler
- **File**: `src/lambdas/dashboard/router_v2.py`
- **Function**: `revoke_sessions_bulk()`
- **Change**: `async def revoke_sessions_bulk(request: Request, body: BulkRevocationRequest, ...)`

### T004: Create Unit Tests
- [ ] Create test file `tests/unit/lambdas/dashboard/test_admin_sessions_revoke_auth.py`
- **Tests to implement**:
  - `test_revoke_without_jwt_returns_401`
  - `test_revoke_without_operator_role_returns_403`
  - `test_revoke_with_operator_role_succeeds`
  - `test_error_message_generic`

### T005: Run Unit Tests
- [ ] Execute `pytest tests/unit/lambdas/dashboard/ -v --tb=short`
- [ ] Verify all tests pass
- [ ] Verify no regression in existing tests

### T006: Commit and Push
- [ ] Stage changes
- [ ] Commit with conventional format
- [ ] Push and create PR
- [ ] Enable auto-merge

## Acceptance Verification

- [ ] Endpoint returns 401 without JWT
- [ ] Endpoint returns 403 without operator role
- [ ] Endpoint allows operator role access
- [ ] Error messages are generic (no role enumeration)
- [ ] All unit tests pass
- [ ] No regression in existing functionality
