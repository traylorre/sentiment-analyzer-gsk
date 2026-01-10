# Tasks: OAuth State Validation

**Feature**: 1185-oauth-state-validation
**Created**: 2026-01-10
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 10 |
| Phase 1 (Setup) | 1 |
| Phase 2 (US1 - State Generation) | 3 |
| Phase 3 (US2 - State Validation) | 4 |
| Phase 4 (Polish) | 2 |

## Phase 1: Setup

- [ ] T001 Create `src/lambdas/shared/auth/oauth_state.py` with OAuthState dataclass, generate_state(), store_state(), get_state() functions

## Phase 2: User Story 1 - State Generation (P1)

**Goal**: Generate and store OAuth state when URLs are requested

**Independent Test**: Call GET /oauth/urls and verify state is included in response and stored in DynamoDB

- [ ] T002 [US1] Add `state` field to OAuthURLsResponse model in `src/lambdas/dashboard/router_v2.py`
- [ ] T003 [US1] Update `get_oauth_urls()` in `src/lambdas/dashboard/auth.py` to generate state, store in DynamoDB, include in authorize URLs
- [ ] T004 [US1] Add unit tests for state generation in `tests/unit/dashboard/test_oauth_state.py`

## Phase 3: User Story 2 - State Validation (P1)

**Goal**: Validate state on OAuth callback, reject mismatched redirect_uri or provider

**Independent Test**: Attempt callback with invalid state and verify 400 response

- [ ] T005 [US2] Add `state` field to OAuthCallbackRequest model in `src/lambdas/dashboard/router_v2.py`
- [ ] T006 [US2] Add `validate_oauth_state()` function in `src/lambdas/shared/auth/oauth_state.py` with all checks (exists, not expired, not used, provider match, redirect_uri match)
- [ ] T007 [US2] Update `handle_oauth_callback()` in `src/lambdas/dashboard/auth.py` to call validate_oauth_state() before processing
- [ ] T008 [US2] Add unit tests for state validation (expired, used, wrong provider, wrong redirect_uri, valid) in `tests/unit/dashboard/test_oauth_state.py`

## Phase 4: Polish

- [ ] T009 Update existing OAuth tests in `tests/unit/dashboard/test_oauth_callback_federation.py` to include state parameter
- [ ] T010 Run `ruff check src/ tests/ --fix && ruff format src/ tests/` and verify all unit tests pass

## Dependency Graph

```
T001 (create oauth_state.py)
  ↓
T002 (response model) → T003 (get_oauth_urls) → T004 (tests)
  ↓
T005 (request model) → T006 (validate fn) → T007 (callback) → T008 (tests)
  ↓
T009 (update existing tests) → T010 (polish)
```

## Parallel Execution

- T002 and T005 can run in parallel (different models)
- T004 and T008 unit tests can be written as implementation proceeds

## Implementation Strategy

1. **Foundation (T001)**: Create oauth_state.py module
2. **Generation (T002-T004)**: State generation and storage
3. **Validation (T005-T008)**: State validation on callback
4. **Polish (T009-T010)**: Update existing tests, verify all pass

## Notes

- Use generic error messages for all validation failures
- Store state with 5-minute TTL for automatic DynamoDB cleanup
- Mark states as used with conditional update to prevent race conditions
