# Tasks: Fix E2E Test Authentication

**Feature ID**: 1053
**Input**: spec.md
**Approach**: Option A - Test-Only JWT Generation

## Phase 1: Create JWT Authentication Fixture

- [ ] T001 Create `authenticated_api_client` fixture in tests/e2e/conftest.py that generates valid JWT tokens using existing PyJWT library
- [ ] T002 Add `PREPROD_TEST_JWT_SECRET` environment variable handling with fallback for local dev
- [ ] T003 Update PreprodAPIClient to use `set_bearer_token()` for JWT auth (verify method exists or add it)

## Phase 2: Update E2E Tests to Use JWT Auth

- [ ] T004 Update tests/e2e/test_alerts.py to use `authenticated_api_client` fixture instead of `set_auth_type("email")`
- [ ] T005 Update tests/e2e/test_notifications.py to use JWT authentication
- [ ] T006 Update tests/e2e/test_live_update_latency.py to use JWT authentication
- [ ] T007 Update tests/integration/test_e2e_lambda_invocation_preprod.py auth tests

## Phase 3: Remove Deprecated Auth Pattern

- [ ] T008 Remove `set_auth_type()` method from PreprodAPIClient (or mark deprecated)
- [ ] T009 Remove all usages of X-Auth-Type header in E2E tests
- [ ] T010 Verify `test_x_auth_type_header_is_ignored` security test still passes

## Phase 4: CI Configuration

- [ ] T011 Add PREPROD_TEST_JWT_SECRET to .github/workflows/deploy.yml preprod environment
- [ ] T012 Ensure JWT_SECRET in Lambda environment matches test secret (or document mismatch handling)

## Phase 5: Verification

- [ ] T013 Run `make validate` to ensure no regressions
- [ ] T014 Run E2E tests locally with test JWT secret to verify fix
- [ ] T015 Verify pipeline passes after deployment

## Dependencies

- T001 must complete before T004-T007
- T002 must complete before T001
- T011 should complete before T015 for CI to pass
- T008-T009 should be done after T004-T007 pass

## Estimated Complexity

- **Medium**: ~15 files modified, new fixture + test updates
- **Risk**: CI secret configuration required for full fix
