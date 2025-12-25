# Feature Specification: Fix E2E Test Authentication After Security Fix

**Feature Branch**: `1053-fix-e2e-auth-tests`
**Created**: 2025-12-24
**Status**: Draft
**Input**: Pipeline failure analysis - E2E tests returning 403 after Feature 1048 security fix

## Problem Statement

E2E tests are failing with 403 "This endpoint requires authenticated user" errors after Feature 1048 blocked the X-Auth-Type header bypass vulnerability.

**Root Cause**: E2E tests in `tests/e2e/test_alerts.py` and related files used `api_client.set_auth_type("email")` which sent `X-Auth-Type: email` header to simulate authenticated users. Feature 1048 correctly blocked this pattern as a security vulnerability (any anonymous user could send this header to bypass authentication checks).

**Affected Tests** (16+ failures):
- `tests/e2e/test_alerts.py` - 5 tests (403)
- `tests/e2e/test_notifications.py` - 4 tests (depends on alerts)
- `tests/e2e/test_live_update_latency.py` - 3 tests (no SSE events)
- `tests/integration/test_e2e_lambda_invocation_preprod.py` - 2 tests (auth rejection)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - E2E Tests Pass in CI (Priority: P0)

As a developer, I want E2E tests to pass in CI after the security fix, so that the deploy pipeline can reach production.

**Why this priority**: Blocking all deployments to production.

**Independent Test**: Run `pytest tests/e2e/test_alerts.py -v` against preprod environment and verify tests pass.

**Acceptance Scenarios**:

1. **Given** Feature 1048 is deployed (X-Auth-Type blocked), **When** E2E tests run, **Then** tests that require authenticated users use proper authentication mechanism
2. **Given** an anonymous session token, **When** an alert endpoint is called, **Then** the system correctly returns 403 (current behavior, tests should expect this)
3. **Given** the test environment, **When** tests need authenticated access, **Then** they use a test-specific authentication path that doesn't reintroduce the vulnerability

---

### User Story 2 - Security Not Compromised (Priority: P0)

As a security engineer, I want the test fix to not reintroduce the X-Auth-Type bypass vulnerability, so that production remains secure.

**Why this priority**: Cannot regress security to fix tests.

**Independent Test**: Verify that X-Auth-Type header is still ignored by the auth middleware.

**Acceptance Scenarios**:

1. **Given** an anonymous session, **When** X-Auth-Type: email header is sent, **Then** the user is still treated as anonymous
2. **Given** the test authentication mechanism, **When** it's analyzed, **Then** it does not expose a production attack vector

---

### Edge Cases

- What if tests legitimately need authenticated access? Use preprod-only test authentication route or synthetic JWT.
- What if SSE tests fail due to auth? They likely need the same auth fix.
- What if notification tests depend on alert creation? Fix cascades from alert tests.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Remove usage of `set_auth_type()` / `X-Auth-Type` header from E2E tests
- **FR-002**: Tests requiring authenticated access MUST use one of:
  - (a) Test-specific JWT token generation for preprod environment, OR
  - (b) Update tests to verify anonymous-accessible behavior only, OR
  - (c) Mark tests as skipped with remediation note if auth is unavailable
- **FR-003**: Tests MUST NOT reintroduce X-Auth-Type header bypass
- **FR-004**: SSE/live update tests must use same auth mechanism

### Non-Functional Requirements

- **NFR-001**: Fix should not require production code changes
- **NFR-002**: Tests should remain meaningful (not just skip everything)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `pytest tests/e2e/ -m preprod -v` passes with ≤5% skip rate for auth-related tests
- **SC-002**: Deploy pipeline reaches production (preprod integration tests pass)
- **SC-003**: Security test `test_x_auth_type_header_is_ignored` continues to pass
- **SC-004**: No X-Auth-Type header usage in test codebase

## Technical Approach

### Option A: Test-Only JWT Generation (Recommended)

Add a test fixture that generates valid JWT tokens for preprod using a test-specific secret:

```python
@pytest.fixture
def authenticated_api_client(api_client, preprod_jwt_secret):
    """Create API client with real JWT authentication for E2E tests."""
    token = generate_test_jwt(user_id=str(uuid4()), secret=preprod_jwt_secret)
    api_client.set_bearer_token(token)
    return api_client
```

Pros: Tests real authentication flow
Cons: Requires preprod-accessible test secret

### Option B: Mark Tests as Requiring Auth Setup

Tests that require authenticated users are marked with a skip condition until proper auth infrastructure is set up:

```python
@pytest.mark.skipif(
    not os.environ.get("PREPROD_TEST_JWT_SECRET"),
    reason="Authenticated tests require PREPROD_TEST_JWT_SECRET"
)
async def test_alert_create_sentiment_threshold(...):
```

Pros: Non-breaking, documents requirement
Cons: Reduces test coverage temporarily

### Option C: Update Tests to Test Anonymous Behavior

Change tests to verify that anonymous users correctly get 403:

```python
async def test_alert_create_requires_authentication(...):
    """Verify anonymous users cannot create alerts (security requirement)."""
    response = await api_client.post(f"/api/v2/configurations/{config_id}/alerts", ...)
    assert response.status_code == 403
```

Pros: Tests become security validations
Cons: Loses functional coverage of alert CRUD

## Assumptions

- Preprod environment can have a test-specific JWT secret configured
- The security fix in Feature 1048 is correct and should not be reverted
- Some tests may need to become "authenticated feature not available" skip tests

## Dependencies

- Feature 1048 (already merged) - X-Auth-Type header blocking
- Preprod infrastructure may need JWT secret for test authentication

## Out of Scope

- Changes to production auth middleware
- Reintroducing X-Auth-Type header bypass
- Magic link or OAuth flow testing (separate concern)
