# Tasks: Guard Mock Token Generation

**Feature Branch**: `1128-guard-mock-tokens`
**Generated**: 2026-01-05
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 6 |
| User Story 1 Tasks | 2 |
| User Story 2 Tasks | 1 |
| User Story 3 Tasks | 1 |
| Parallel Opportunities | 0 (sequential due to dependencies) |
| MVP Scope | US1 + US2 (security + dev workflow) |

## User Stories (from spec.md)

| Story | Priority | Description | Independent Test |
|-------|----------|-------------|------------------|
| US1 | P1 | Production Lambda Rejects Mock Tokens | Set AWS_LAMBDA_FUNCTION_NAME, verify RuntimeError |
| US2 | P1 | Local Development Continues to Work | Unset env var, verify tokens generated |
| US3 | P2 | Clear Error Messages for Debugging | Verify error message contains actionable info |

## Dependencies

```
Phase 1: Setup
    ↓
Phase 2: US1 (Production Guard) + US2 (Local Dev) + US3 (Error Messages)
    ↓
Phase 3: Polish (Validation)
```

Note: US1, US2, and US3 are implemented together in a single function change. They cannot be parallelized as they modify the same code block.

---

## Phase 1: Setup

> No setup tasks needed - this feature modifies existing code with no new dependencies.

---

## Phase 2: Implementation (US1 + US2 + US3)

**Goal**: Add environment guard to `_generate_tokens()` that blocks mock tokens in Lambda while preserving local development workflow.

**Independent Test**:
- US1: With `AWS_LAMBDA_FUNCTION_NAME` set, call `_generate_tokens()` → expect RuntimeError
- US2: Without env var, call `_generate_tokens()` → expect mock tokens returned
- US3: Check RuntimeError message contains "Cognito" guidance

### Tasks

- [x] T001 [US1] [US2] [US3] Add Lambda environment guard to `_generate_tokens()` function in `src/lambdas/dashboard/auth.py`
  - Add guard check at function start: `if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):`
  - Log error at ERROR level with security message
  - Raise RuntimeError with descriptive message mentioning Cognito
  - Keep existing mock token generation unchanged (for local dev)

- [x] T002 [US1] [US2] [US3] Create unit tests for environment guard in `tests/unit/lambdas/dashboard/test_auth_guard.py`
  - Test: Lambda environment (AWS_LAMBDA_FUNCTION_NAME set) → RuntimeError raised
  - Test: Local environment (no env var) → mock tokens generated correctly
  - Test: Empty string env var → mock tokens generated (empty is falsy)
  - Test: Error message contains "Cognito" and "production"
  - Test: Verify tokens format unchanged for local dev

---

## Phase 3: Polish & Validation

- [x] T003 Run `make validate` to ensure code passes linting, formatting, and SAST checks
- [x] T004 Run `pytest tests/unit/lambdas/dashboard/test_auth_guard.py -v` to verify all tests pass
- [ ] T005 Verify no existing tests are broken by running `pytest tests/unit/ -v --tb=short`
- [x] T006 Update spec.md status from "Draft" to "Implemented" in `specs/1128-guard-mock-tokens/spec.md`

---

## Implementation Strategy

### MVP (Minimum Viable Product)

US1 + US2 together (T001 + T002) - cannot be separated as they're the same code change tested from different perspectives.

### Incremental Delivery

1. **First commit**: T001 (implementation) + T002 (tests)
2. **Second commit**: T003-T006 (validation and cleanup)

### File Changes Summary

| File | Change Type | Tasks |
|------|-------------|-------|
| `src/lambdas/dashboard/auth.py` | Modify | T001 |
| `tests/unit/lambdas/dashboard/test_auth_guard.py` | Create | T002 |
| `specs/1128-guard-mock-tokens/spec.md` | Modify | T006 |

---

## Acceptance Criteria Traceability

| Requirement | Task | Verification |
|-------------|------|--------------|
| FR-001: Check AWS_LAMBDA_FUNCTION_NAME | T001 | T002 test case |
| FR-002: Raise RuntimeError | T001 | T002 test case |
| FR-003: Allow mock tokens locally | T001 | T002 test case |
| FR-004: Maintain token format | T001 | T002 test case |
| FR-005: Log at ERROR level | T001 | T002 test case |
| SC-001: 100% blocked in Lambda | T002 | Unit test |
| SC-002: 100% success locally | T002 | Unit test |
| SC-003: Logged for audit | T001, T002 | Unit test |
| SC-004: No dev workflow impact | T002 | Unit test |
