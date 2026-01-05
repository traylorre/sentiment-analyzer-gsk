# Tasks: Protect Admin Sessions Revoke Endpoint

**Feature**: 001-protect-admin-sessions
**Date**: 2026-01-05
**Source**: [plan.md](./plan.md), [spec.md](./spec.md)

## Phase 1: Setup

- [x] T001 Verify require_role decorator exists at src/lambdas/shared/middleware/require_role.py

## Phase 2: User Story 1 - Operator Access (P1)

**Goal**: Operators can revoke sessions successfully
**Test Criteria**: Operator with `roles=["operator"]` receives 200 on POST /api/v2/admin/sessions/revoke

- [x] T002 [US1] Add require_role import to src/lambdas/dashboard/router_v2.py
- [x] T003 [US1] Add @require_role("operator") decorator to revoke_sessions_bulk in src/lambdas/dashboard/router_v2.py
- [x] T004 [US1] Add unit test for operator success (200) in tests/unit/lambdas/dashboard/test_revoke_sessions_auth.py

## Phase 3: User Story 2 - Non-Operator Blocked (P1)

**Goal**: Non-operators are blocked from revoking sessions
**Test Criteria**: User with `roles=["free"]` receives 403, unauthenticated receives 401

- [x] T005 [US2] Add unit test for non-operator rejection (403) in tests/unit/lambdas/dashboard/test_revoke_sessions_auth.py
- [x] T006 [US2] Add unit test for unauthenticated rejection (401) in tests/unit/lambdas/dashboard/test_revoke_sessions_auth.py

## Phase 4: Polish

- [x] T007 Run pytest tests/unit/lambdas/dashboard/test_revoke_sessions_auth.py -v to verify all tests pass
- [x] T008 Run ruff check on modified files

## Dependencies

```
T001 → T002 → T003 → T004
                 ↓
              T005, T006 (parallel after T003)
                 ↓
              T007 → T008
```

## Parallel Execution

- T005 and T006 can run in parallel (independent test cases)
- All other tasks are sequential

## Execution Notes

- Total tasks: 8
- All tasks completed
- Files modified: 2 (router_v2.py, test_revoke_sessions_auth.py)
