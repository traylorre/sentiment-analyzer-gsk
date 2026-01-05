# Tasks: Atomic Magic Link Token Consumption

**Feature Branch**: `1129-atomic-magic-link`
**Generated**: 2026-01-05
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 6 |
| User Story 1 Tasks | 2 |
| User Story 2 Tasks | 1 (shared with US1) |
| User Story 3 Tasks | 1 (shared with US1) |
| Parallel Opportunities | 0 (sequential - single file change) |
| MVP Scope | T001 + T002 (router change + tests) |

## User Stories (from spec.md)

| Story | Priority | Description | Independent Test |
|-------|----------|-------------|------------------|
| US1 | P1 | Atomic Token Consumption Prevents Replay | Two concurrent requests → exactly one success |
| US2 | P1 | Expired Tokens Are Rejected | Expired token → 410 Gone |
| US3 | P2 | Audit Trail for Token Consumption | Verify used_at, used_by_ip recorded |

## Dependencies

```
Phase 1: Setup (none needed)
    ↓
Phase 2: US1 + US2 + US3 (single router change covers all)
    ↓
Phase 3: Polish (validation)
```

Note: All user stories are satisfied by a single router change because the atomic function already implements all requirements.

---

## Phase 1: Setup

> No setup tasks needed - this feature uses existing atomic function, no new dependencies.

---

## Phase 2: Implementation (US1 + US2 + US3)

**Goal**: Update router to call `verify_and_consume_token()` instead of `verify_magic_link()`, passing client IP for audit.

**Independent Tests**:
- US1: Two concurrent requests with same token → one 200, one 409
- US2: Expired token request → 410 Gone
- US3: Check DynamoDB record has `used_at` and `used_by_ip` after consumption

### Tasks

- [X] T001 [US1] [US2] [US3] Update magic link verification endpoint to use atomic function in `src/lambdas/dashboard/router_v2.py`
  - Change line ~348 from `verify_magic_link(token)` to `verify_and_consume_token(token, client_ip)`
  - Extract client IP from request (e.g., `request.client.host` or `X-Forwarded-For` header)
  - Ensure error handling for `TokenAlreadyUsedError` → 409 and `TokenExpiredError` → 410 is preserved

- [X] T002 [US1] [US2] [US3] Create unit tests for atomic router integration in `tests/unit/lambdas/dashboard/test_atomic_magic_link_router.py`
  - Test: Router calls `verify_and_consume_token` (not `verify_magic_link`)
  - Test: Client IP is passed for audit trail
  - Test: `TokenAlreadyUsedError` returns 409 Conflict
  - Test: `TokenExpiredError` returns 410 Gone
  - Test: Successful verification returns 200 with tokens

---

## Phase 3: Polish & Validation

- [X] T003 Run `make validate` to ensure code passes linting, formatting, and SAST checks
- [X] T004 Run `pytest tests/unit/lambdas/dashboard/test_atomic_magic_link_router.py -v` to verify all tests pass
- [X] T005 Verify no existing tests are broken by running `pytest tests/unit/ -v --tb=short`
- [X] T006 Update spec.md status from "Draft" to "Implemented" in `specs/1129-atomic-magic-link/spec.md`

---

## Implementation Strategy

### MVP (Minimum Viable Product)

T001 + T002 together - single router change with comprehensive tests.

### Incremental Delivery

1. **First commit**: T001 (router change) + T002 (tests)
2. **Second commit**: T003-T006 (validation and cleanup)

### File Changes Summary

| File | Change Type | Tasks |
|------|-------------|-------|
| `src/lambdas/dashboard/router_v2.py` | Modify | T001 |
| `tests/unit/lambdas/dashboard/test_atomic_magic_link_router.py` | Create | T002 |
| `specs/1129-atomic-magic-link/spec.md` | Modify | T006 |

---

## Acceptance Criteria Traceability

| Requirement | Task | Verification |
|-------------|------|--------------|
| FR-001: Conditional database update | Existing | `verify_and_consume_token` already implements |
| FR-002: 200 OK on success | T001 | T002 test case |
| FR-003: 409 Conflict on used | T001 | T002 test case |
| FR-004: 410 Gone on expired | T001 | T002 test case |
| FR-005: Record used_at | Existing | `verify_and_consume_token` already implements |
| FR-006: Record used_by_ip | T001 | T002 test case (passes client_ip) |
| FR-007: Use atomic function | T001 | T002 test case |
| SC-001: Concurrent requests | T002 | Unit test with mock |
| SC-002: Expired rejection | T002 | Unit test |
| SC-003: Audit records | T001, T002 | Client IP passed to function |
| SC-004: No replay bypass | T001 | Uses atomic function |
