# Tasks: OAuth Role Advancement

**Feature**: 1170-oauth-role-advancement
**Date**: 2026-01-07
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 0 | Setup (N/A - existing project) |
| 2 | 1 | Foundational - create _advance_role() helper |
| 3 | 2 | US1/US2 - integrate into OAuth flow + tests |
| 4 | 1 | Polish - verify edge cases |

**Total Tasks**: 4
**Parallel Opportunities**: T003 and T004 can run in parallel (tests and integration)

## Phase 2: Foundational

### Goal: Create the _advance_role() helper function

- [ ] T001 Create `_advance_role()` function in `src/lambdas/dashboard/auth.py` after `_link_provider()` (~line 1740)
  - Parameters: `user: User`, `provider: str`, `table: dynamodb.Table`
  - If `user.role == "anonymous"`: update to "free", set `role_assigned_at`, set `role_assigned_by = f"oauth:{provider}"`
  - If role is already "free"/"paid"/"operator": return user unchanged
  - Use same DynamoDB update pattern as `_link_provider()`
  - Follow silent failure pattern (log warning, don't break OAuth)

## Phase 3: User Stories 1 & 2 - Role Advancement + Audit Trail

### Goal: Integrate role advancement into OAuth callback and add tests

**Independent Test**: Complete OAuth as anonymous user, verify role="free" and audit fields populated

- [ ] T002 Integrate `_advance_role()` call in `handle_oauth_callback()` in `src/lambdas/dashboard/auth.py`
  - Call after `_link_provider()` for both new and existing user paths
  - Pass provider name (google/github) for audit trail

- [ ] T003 [P] Create unit tests in `tests/unit/dashboard/test_role_advancement.py`
  - Test: anonymous → free advancement (role changes, audit fields set)
  - Test: free user stays free (no update called)
  - Test: paid user stays paid (no update called)
  - Test: operator stays operator (no update called)
  - Test: role_assigned_by format is "oauth:google" or "oauth:github"
  - Test: role_assigned_at is valid ISO timestamp
  - Test: DynamoDB UpdateItem called with correct parameters

## Phase 4: Polish

### Goal: Verify edge cases and error handling

- [ ] T004 [P] Verify edge case handling in `src/lambdas/dashboard/auth.py`
  - Ensure role advancement failure doesn't break OAuth flow
  - Ensure logging captures role advancement events
  - Ensure existing users linking OAuth also get role advancement

## Dependencies

```text
T001 (create function)
  ↓
T002 (integrate into OAuth)
  ↓
T003, T004 (parallel: tests + edge cases)
```

## Implementation Strategy

1. **MVP**: T001 + T002 = working role advancement
2. **Quality**: T003 = test coverage
3. **Hardening**: T004 = edge case verification

All tasks modify existing `auth.py` or create one new test file. No new dependencies required.
