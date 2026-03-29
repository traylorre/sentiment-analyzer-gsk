# Tasks: CORS Wildcard Origin Fix

**Input**: Design documents from `/specs/1268-cors-wildcard-fix/`
**Prerequisites**: plan.md (loaded), spec.md (loaded), research.md (loaded)

**Tests**: INCLUDED -- feature specification mandates tests at every layer (unit, integration, E2E, Playwright).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Infrastructure**: `infrastructure/terraform/modules/api_gateway/`
- **Root module**: `infrastructure/terraform/`
- **Tests**: `tests/unit/`, `tests/integration/`, `tests/e2e/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the `cors_allowed_origins` variable to the API Gateway module and wire it from the root module.

- [ ] T001 Add `cors_allowed_origins` variable (type `list(string)`, default `[]`) with wildcard validation to `infrastructure/terraform/modules/api_gateway/variables.tf`
- [ ] T002 Pass `cors_allowed_origins = var.cors_allowed_origins` from root module invocation of `module.api_gateway` in `infrastructure/terraform/main.tf` (around line 805)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Fix all three wildcard locations and add missing headers. MUST complete before any testing.

**CRITICAL**: No user story validation can begin until all three wildcard locations are fixed.

- [ ] T003 Replace `"'*'"` with `"method.request.header.Origin"` in `local.cors_headers` for `Access-Control-Allow-Origin` at line 212 of `infrastructure/terraform/modules/api_gateway/main.tf`
- [ ] T004 Add `"method.response.header.Vary" = "'Origin'"` to `local.cors_headers` in `infrastructure/terraform/modules/api_gateway/main.tf` (line ~209-214)
- [ ] T005 Update `proxy_options` method_response (line ~595-607) in `infrastructure/terraform/modules/api_gateway/main.tf`: add `"method.response.header.Access-Control-Allow-Credentials" = true` and `"method.response.header.Vary" = true` to `response_parameters`
- [ ] T006 Update `proxy_options` integration_response (line ~610-622) in `infrastructure/terraform/modules/api_gateway/main.tf`: replace `"method.response.header.Access-Control-Allow-Origin" = "'*'"` with `"method.response.header.Access-Control-Allow-Origin" = "method.request.header.Origin"`, add `"method.response.header.Access-Control-Allow-Credentials" = "'true'"`, add `"method.response.header.Vary" = "'Origin'"`
- [ ] T007 Update `root_options` method_response (line ~655-667) in `infrastructure/terraform/modules/api_gateway/main.tf`: add `"method.response.header.Access-Control-Allow-Credentials" = true` and `"method.response.header.Vary" = true` to `response_parameters`
- [ ] T008 Update `root_options` integration_response (line ~670-682) in `infrastructure/terraform/modules/api_gateway/main.tf`: replace `"method.response.header.Access-Control-Allow-Origin" = "'*'"` with `"method.response.header.Access-Control-Allow-Origin" = "method.request.header.Origin"`, add `"method.response.header.Access-Control-Allow-Credentials" = "'true'"`, add `"method.response.header.Vary" = "'Origin'"`
- [ ] T009 Add `"method.response.header.Vary"` declaration (set to `true`) to all method_response resources that use `local.cors_headers`: `fr012_options`, `fr012_proxy_options`, `public_leaf_options`, `public_proxy_options` in `infrastructure/terraform/modules/api_gateway/main.tf`
- [ ] T010 Run `terraform fmt` and `terraform validate` on `infrastructure/terraform/` to verify no syntax errors

**Checkpoint**: All wildcards removed, origin echoing in place, Vary header added. Terraform validates clean.

---

## Phase 3: User Story 1 - Authenticated Dashboard User Makes API Calls (Priority: P1) MVP

**Goal**: Verify that credentialed API calls from allowed origins succeed with correct CORS headers.

**Independent Test**: Make a credentialed fetch from an allowed origin and confirm the response includes the echoed origin (not wildcard).

### Tests for User Story 1

- [ ] T011 [P] [US1] Add unit test `test_cors_no_wildcard_origin` to `tests/unit/test_api_gateway_cognito.py` in the `TestCORSOnErrorResponses` class: parse `infrastructure/terraform/modules/api_gateway/main.tf` and assert no `response_parameters` value contains the literal string `"'*'"` for any `Access-Control-Allow-Origin` key
- [ ] T012 [P] [US1] Add unit test `test_cors_uses_origin_echoing` to `tests/unit/test_api_gateway_cognito.py`: assert all `Access-Control-Allow-Origin` integration response values use `method.request.header.Origin` (or `method.request.header.origin`)
- [ ] T013 [P] [US1] Add unit test `test_cors_credentials_present_on_all_options` to `tests/unit/test_api_gateway_cognito.py`: assert all OPTIONS integration responses include `Access-Control-Allow-Credentials` set to `'true'`
- [ ] T014 [P] [US1] Add unit test `test_cors_vary_origin_present` to `tests/unit/test_api_gateway_cognito.py`: assert all OPTIONS integration responses include `Vary` header set to `'Origin'`
- [ ] T015 [P] [US1] Create integration test file `tests/integration/test_cors_headers.py` with test `test_options_echoes_allowed_origin`: send OPTIONS request to preprod API Gateway endpoint with `Origin: https://main.d29tlmksqcx494.amplifyapp.com` and assert response `Access-Control-Allow-Origin` equals the sent origin
- [ ] T016 [P] [US1] Add integration test `test_options_includes_credentials` in `tests/integration/test_cors_headers.py`: send OPTIONS and assert `Access-Control-Allow-Credentials: true` is present
- [ ] T017 [P] [US1] Add integration test `test_options_includes_vary_origin` in `tests/integration/test_cors_headers.py`: send OPTIONS and assert `Vary: Origin` is present

### Implementation for User Story 1

Implementation is fully covered by Phase 2 (T003-T010). No additional implementation tasks needed for US1.

**Checkpoint**: Unit tests pass confirming HCL has no wildcard. Integration tests pass confirming deployed API echoes origin.

---

## Phase 4: User Story 2 - Local Developer Testing (Priority: P2)

**Goal**: Verify localhost origins work correctly in preprod environment.

**Independent Test**: Send OPTIONS with `Origin: http://localhost:3000` to preprod API and confirm echoed.

### Tests for User Story 2

- [ ] T018 [P] [US2] Add integration test `test_options_echoes_localhost_origin` in `tests/integration/test_cors_headers.py`: send OPTIONS with `Origin: http://localhost:3000` and assert echoed back
- [ ] T019 [P] [US2] Add integration test `test_options_echoes_localhost_alt_port` in `tests/integration/test_cors_headers.py`: send OPTIONS with `Origin: http://localhost:8080` and assert echoed back

### Implementation for User Story 2

Implementation is fully covered by Phase 2 (origin echoing works for any origin). No additional implementation tasks.

**Checkpoint**: localhost origins work correctly in preprod environment.

---

## Phase 5: User Story 3 - Unauthorized Origin Rejection (Priority: P2)

**Goal**: Verify that unauthorized origins cannot exfiltrate data via credentialed requests (Lambda-level validation).

**Independent Test**: Send GET with unauthorized origin and credentials; assert Lambda rejects the origin in its response headers.

### Tests for User Story 3

- [ ] T020 [P] [US3] Add integration test `test_options_echoes_any_origin_mock_behavior` in `tests/integration/test_cors_headers.py`: send OPTIONS with `Origin: https://evil.example.com` and assert it IS echoed (expected MOCK behavior; documents that OPTIONS is not the security boundary)
- [ ] T021 [P] [US3] Add integration test `test_get_rejects_unauthorized_origin` in `tests/integration/test_cors_headers.py`: send GET to a data endpoint with `Origin: https://evil.example.com` and valid auth credentials, assert response `Access-Control-Allow-Origin` does NOT contain `https://evil.example.com` (Lambda middleware rejects)
- [ ] T022 [P] [US3] Add integration test `test_get_accepts_authorized_origin` in `tests/integration/test_cors_headers.py`: send GET to a data endpoint with `Origin: https://main.d29tlmksqcx494.amplifyapp.com` and valid auth credentials, assert response `Access-Control-Allow-Origin` matches the sent origin

### Implementation for User Story 3

Implementation is fully covered by Phase 2 (origin echoing) and existing Lambda middleware. No additional implementation tasks.

**Checkpoint**: Unauthorized origins cannot read data responses.

---

## Phase 6: User Story 4 - Infrastructure Consistency (Priority: P3)

**Goal**: Verify all response types (OPTIONS, 401, 403, 200) use consistent origin-echoing pattern.

**Independent Test**: Compare CORS headers across different response types from the same origin.

### Tests for User Story 4

- [ ] T023 [P] [US4] Add unit test `test_all_cors_origin_values_consistent` in `tests/unit/test_api_gateway_cognito.py`: parse `main.tf` and assert every `Access-Control-Allow-Origin` value (in gateway responses, integration responses, and cors_headers local) uses `method.request.header.Origin` or `method.request.header.origin` (no wildcards, no static values)
- [ ] T024 [P] [US4] Add integration test `test_401_error_echoes_origin` in `tests/integration/test_cors_headers.py`: send request that triggers 401 with `Origin` header, assert origin is echoed in error response
- [ ] T025 [P] [US4] Add integration test `test_403_error_echoes_origin` in `tests/integration/test_cors_headers.py`: send request that triggers 403 with `Origin` header, assert origin is echoed in error response

### Implementation for User Story 4

Implementation is fully covered by Phase 2 and existing gateway responses (which already echo origin). No additional implementation tasks.

**Checkpoint**: All response types use consistent origin-echoing pattern.

---

## Phase 7: E2E and Playwright Tests

**Purpose**: End-to-end validation and browser-level implicit CORS testing.

- [ ] T026 [P] Create E2E test file `tests/e2e/test_cors_e2e.py` with test `test_authenticated_api_call_succeeds`: perform full authentication flow against preprod, make credentialed API call, verify response received (implicit CORS validation)
- [ ] T027 [P] Add Playwright test (if existing test infrastructure supports it) in appropriate Playwright test file: verify dashboard loads and displays data after authentication (implicit CORS validation; no explicit header assertions per AR1-05)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and cleanup.

- [ ] T028 [P] Add entry to `docs/ci-gotchas.md` documenting the CORS wildcard + credentials gotcha: problem, symptom, fix, prevention
- [ ] T029 [P] Add `test_cors_no_wildcard_with_credentials` to existing CORS validator in template repo if applicable (`src/validators/` in terraform-gsk-template)
- [ ] T030 Run `make validate` to ensure all validators pass
- [ ] T031 Run full test suite: `make test-local` to verify no regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion -- BLOCKS all testing
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User story test phases can proceed in parallel
  - Implementation for ALL stories is in Phase 2 (infrastructure-only change)
- **E2E/Playwright (Phase 7)**: Depends on deployment of Phase 2 changes to preprod
- **Polish (Phase 8)**: Depends on all test phases passing

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 -- no dependencies on other stories
- **User Story 2 (P2)**: Can start after Phase 2 -- independent of US1
- **User Story 3 (P2)**: Can start after Phase 2 -- independent of US1/US2
- **User Story 4 (P3)**: Can start after Phase 2 -- independent of other stories

### Within Each User Story

- Tests can be written in parallel (all marked [P])
- Tests verify behavior of Phase 2 implementation
- No implementation tasks within stories (all implementation is in Phase 2)

### Parallel Opportunities

- T001 and T002 are sequential (T002 depends on T001)
- T003-T009 can be batched as a single edit session (all in same file)
- T011-T014 can run in parallel (different test functions, same file)
- T015-T017 can run in parallel (different test functions, same file)
- T018-T019 can run in parallel
- T020-T022 can run in parallel
- T023-T025 can run in parallel
- T026-T027 can run in parallel
- T028-T029 can run in parallel

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all unit tests for US1 together:
Task: "T011 - test_cors_no_wildcard_origin in tests/unit/test_api_gateway_cognito.py"
Task: "T012 - test_cors_uses_origin_echoing in tests/unit/test_api_gateway_cognito.py"
Task: "T013 - test_cors_credentials_present_on_all_options in tests/unit/test_api_gateway_cognito.py"
Task: "T014 - test_cors_vary_origin_present in tests/unit/test_api_gateway_cognito.py"

# Launch all integration tests for US1 together:
Task: "T015 - test_options_echoes_allowed_origin in tests/integration/test_cors_headers.py"
Task: "T016 - test_options_includes_credentials in tests/integration/test_cors_headers.py"
Task: "T017 - test_options_includes_vary_origin in tests/integration/test_cors_headers.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T010)
3. Complete Phase 3: User Story 1 tests (T011-T017)
4. **STOP and VALIDATE**: All unit and integration tests pass for US1
5. Deploy if ready -- core CORS bug is fixed

### Incremental Delivery

1. Phase 1-2: Infrastructure changes deployed -- core fix live
2. Phase 3: US1 tests confirm allowed origins work
3. Phase 4: US2 tests confirm localhost works
4. Phase 5: US3 tests confirm unauthorized origin rejection at Lambda layer
5. Phase 6: US4 tests confirm consistency across all response types
6. Phase 7: E2E confirms full stack works
7. Phase 8: Documentation and polish

### Notes

- This feature is infrastructure-heavy: ALL implementation is in Phase 2 (Terraform changes)
- User story phases are test-only: they verify the Phase 2 implementation
- The 31 tasks break down as: 2 setup + 8 foundational + 7 US1 tests + 2 US2 tests + 3 US3 tests + 3 US4 tests + 2 E2E + 4 polish
- Suggested MVP: Phases 1-3 (12 tasks total, delivers the core fix with unit + integration test coverage)

---

## Adversarial Review #3

**Reviewer perspective**: Implementation readiness auditor. Final check across spec, plan, and tasks.

### Cross-Artifact Traceability

| Spec FR | Plan Change | Tasks | Verdict |
|---------|-------------|-------|---------|
| FR-001 | Change 1,2,3 | T003, T006, T008, T012, T015 | TRACED |
| FR-002 | Change 1,2,3 | T003, T006, T008, T011 | TRACED |
| FR-003 (amended) | "Why Echo Is Safe" | T020, T021, T022 | TRACED |
| FR-004 | Change 4 | T001, T002 | TRACED |
| FR-005 | Change 1 matches gateway pattern | T023 | TRACED |
| FR-006 | Plan preserves other headers | T003-T008 (implicit) | TRACED |
| FR-007 (MUST) | Change 6 | T004, T009, T014, T017 | TRACED |
| FR-008 | Existing root validation | No new task (existing) | ACCEPTABLE |
| FR-009 | Same tfvars source | T001, T002 (wiring) | TRACED |

### Finding AR3-01: LOW - Original FR-003 Not Replaced in Spec Body

The original FR-003 at spec.md line 85 still says "MUST omit" but the amended version in the AR1 section says "echoes verbatim." This is a documentation inconsistency, not a functional issue, since the implementation follows the amended version.

**Status**: ACCEPTED -- cosmetic. Can be cleaned up during implementation.

### Finding AR3-02: LOW - T027 Conditional Phrasing

T027 says "if existing test infrastructure supports it" which creates ambiguity for an implementer. Playwright test infrastructure does exist in this repo, so this should be a definitive task.

**Status**: ACCEPTED -- implementer should attempt the task and mark DEFERRED only if infeasible.

### Finding AR3-03: LOW - No Explicit Test for `cors_allowed_origins` Variable Validation

FR-008 requires wildcard rejection in the allowlist. The root module's `variables.tf` already has this validation, but there's no test asserting it. Since this validation pre-existed and is not being changed, no new test is strictly needed.

**Status**: ACCEPTED -- out of scope for this feature.

### Finding AR3-04: INFO - Task Count Reasonable for Scope

31 tasks for a 3-location infrastructure fix may seem high, but the mandatory test-at-every-layer requirement drives the count. 10 implementation tasks + 17 test tasks + 4 polish = appropriate.

### Readiness Assessment

| Criterion | Status |
|-----------|--------|
| All FRs traced to tasks | PASS (9/9) |
| All tasks have file paths | PASS (31/31) |
| Dependency order is sound | PASS |
| No circular dependencies | PASS |
| Constitution alignment | PASS |
| Critical issues | NONE |
| High issues | NONE |
| Blocking items | NONE |

### Verdict: READY

All artifacts are internally consistent, properly traced, and ready for implementation. The feature can proceed to `/speckit.implement` with confidence.

**Recommended execution**: Start with MVP (Phases 1-3, 17 tasks) to deliver the core fix with unit + integration test coverage. Add remaining phases incrementally.
