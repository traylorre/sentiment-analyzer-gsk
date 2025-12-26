# Feature Specification: E2E Test for /api/v2/metrics Auth Scenarios

**Feature Branch**: `1059-e2e-metrics-auth`
**Created**: 2025-12-25
**Status**: Draft
**Input**: Add E2E test for /api/v2/metrics endpoint testing all auth scenarios. Current E2E tests only test /api/v2/metrics/dashboard (wrong endpoint). This test gap masked a 401 bug for days because the correct endpoint was never tested in E2E.

## Problem Statement

The E2E test suite has a critical gap: `test_dashboard_buffered.py:180` tests `/api/v2/metrics/dashboard` but the actual dashboard frontend calls `/api/v2/metrics`. This mismatch allowed a 401 bug to persist undetected for days while all E2E tests passed.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Metrics Endpoint Auth Verification (Priority: P1)

As a developer, I want E2E tests that verify the `/api/v2/metrics` endpoint auth behavior matches the frontend's expectations so that auth bugs are caught before deployment.

**Why this priority**: Without E2E coverage for the actual endpoint the frontend uses, auth bugs can go undetected for days, blocking the demo-able dashboard goal.

**Independent Test**: Can be fully tested by calling `/api/v2/metrics` with various auth headers and verifying responses match expected status codes.

**Acceptance Scenarios**:

1. **Given** no auth headers are present, **When** GET /api/v2/metrics is called, **Then** the response status is 401 and the detail contains "Missing user identification".

2. **Given** an anonymous session token is obtained via POST /api/v2/auth/anonymous, **When** GET /api/v2/metrics is called with X-User-ID header, **Then** the response status is 200 and contains metrics data.

3. **Given** a valid JWT token is available, **When** GET /api/v2/metrics is called with Authorization: Bearer header, **Then** the response status is 200 and contains metrics data.

---

### User Story 2 - Prevent Test/Code Endpoint Mismatch (Priority: P2)

As a developer, I want the E2E test to explicitly document that it tests `/api/v2/metrics` (not `/api/v2/metrics/dashboard`) so that future developers understand the distinction.

**Acceptance Scenarios**:

1. **Given** the test file docstring, **When** a developer reads it, **Then** it clearly states the endpoint being tested is `/api/v2/metrics`.

2. **Given** the test code, **When** reviewed, **Then** the endpoint path is `/api/v2/metrics` without the `/dashboard` suffix.

---

### Edge Cases

- What happens when X-User-ID contains an invalid UUID format? Should return 401 (handled by middleware validation).
- What happens when JWT is expired? Should return 401.
- What happens when JWT is malformed? Should return 401.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: E2E test MUST verify `/api/v2/metrics` returns 401 when no auth headers are present.
- **FR-002**: E2E test MUST verify `/api/v2/metrics` returns 200 with valid anonymous session (X-User-ID header).
- **FR-003**: E2E test MUST verify `/api/v2/metrics` returns 200 with valid JWT (Authorization: Bearer header).
- **FR-004**: E2E test MUST be placed in a new file `tests/e2e/test_metrics_auth.py` to clearly separate from existing tests.
- **FR-005**: Test file MUST include docstring explaining the endpoint distinction from `/api/v2/metrics/dashboard`.

### Key Entities

- **PreprodAPIClient**: The async HTTP client that handles auth headers (tests/e2e/helpers/api_client.py).
- **/api/v2/metrics endpoint**: The dashboard metrics endpoint in handler.py:419-483.
- **X-User-ID header**: Anonymous session auth mechanism.
- **Authorization: Bearer header**: JWT auth mechanism.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Running `pytest tests/e2e/test_metrics_auth.py -v` in preprod passes all 3 auth scenarios.
- **SC-002**: Test file explicitly calls `/api/v2/metrics` (verified by grep on test file).
- **SC-003**: Auth failure (401) scenario is tested before success scenarios (fail-first verification).
- **SC-004**: Tests use existing `api_client` fixture and auth patterns from conftest.py.

## Assumptions

- The preprod environment has the dashboard Lambda deployed with `/api/v2/metrics` endpoint.
- The `api_client` fixture from `tests/e2e/conftest.py` is available.
- Anonymous session creation via `POST /api/v2/auth/anonymous` is functional.

## Implementation Notes

The test should follow existing patterns in `test_auth_anonymous.py` and `test_dashboard_buffered.py`:

1. Create session: `await api_client.post("/api/v2/auth/anonymous", json={})`
2. Set auth: `api_client.set_access_token(token)`
3. Call endpoint: `await api_client.get("/api/v2/metrics")`
4. Clear auth in finally block: `api_client.clear_access_token()`

For JWT testing, use `authenticated_api_client` fixture from conftest.py:547-570.
