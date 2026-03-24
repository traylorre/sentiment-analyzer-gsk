# Feature Specification: Admin Dashboard Lockdown

**Feature Branch**: `1249-admin-dashboard-lockdown`
**Created**: 2026-03-23
**Status**: Draft (post-adversarial-review-v2 — expanded scope from security posture audit)
**Input**: "Lock down admin HTMX dashboard, fix information leakage, fix missing auth, enforce session validation"

## Context

The Dashboard Lambda serves both the REST API (`/api/v2/*`) and the internal admin HTMX dashboard (`/`, `/chaos`, `/static/*`) on the same Function URL. In production, the admin dashboard is accessible to anyone on the internet without authentication. This exposes:
- The full admin HTMX dashboard with operational metrics, sentiment distribution charts, and tag analysis
- The chaos testing UI with experiment configuration and execution controls
- Static assets (JS, CSS) that reveal internal implementation details

The customer-facing dashboard is a separate Next.js app on Amplify. The HTMX dashboard is an internal debugging tool that should not be publicly accessible in production.

### Out of Scope

- Moving the admin dashboard to a separate Lambda (architectural change — too large for this fix)
- Adding WAF rules (separate feature)
- Modifying the customer-facing Next.js dashboard (unaffected)
- Chaos API route gating (`/chaos/experiments/*`) — assigned to Feature 1250
- Chaos experiment duration enforcement — assigned to Feature 1250
- Rate limiting on session creation — assigned to future feature
- User enumeration on check-email — assigned to future feature

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Admin Routes Return 404 in Production (Priority: P1)

In production (and preprod), requesting the admin dashboard routes (`/`, `/chaos`, `/static/*`) returns HTTP 404 with no content. In local development, these routes continue to work normally for developer debugging.

**Why this priority**: This is the single most critical pen-test finding — an internal tool is publicly accessible.

**Acceptance Scenarios**:

1. **Given** the environment is `preprod` or `prod`, **When** a request hits `GET /`, **Then** the response is HTTP 404 with `{"detail": "Not found"}`.
2. **Given** the environment is `preprod` or `prod`, **When** a request hits `GET /chaos`, **Then** HTTP 404.
3. **Given** the environment is `preprod` or `prod`, **When** a request hits `GET /static/app.js`, **Then** HTTP 404.
4. **Given** the environment is `local` or `dev`, **When** a request hits `GET /`, **Then** the admin dashboard HTML is served normally (developer workflow preserved).
5. **Given** the environment is `preprod` or `prod`, **When** a request hits `GET /health`, **Then** the response is HTTP 200 with ONLY `{"status":"healthy"}` — no `table` key, no `environment` key (information leakage removed). The status value stays `"healthy"` to avoid breaking deploy smoke tests that grep for `"status"`.
6. **Given** the environment is `preprod`, **When** a Playwright test requests `GET /`, **Then** the test verifies HTTP 404 (regression guard).

### User Story 2 — Runtime Config Stripped in Production (Priority: P2)

`GET /api/v2/runtime` currently returns the SSE Lambda Function URL and environment name to any caller. In production, this endpoint should return only what the frontend needs without exposing internal infrastructure URLs.

**Why this priority**: Exposes the second Lambda Function URL to attackers without any scanning.

**Acceptance Scenarios**:

7. **Given** the environment is `preprod` or `prod`, **When** a request hits `GET /api/v2/runtime`, **Then** the response is `{"sse_url": null, "environment": "production"}` — real SSE URL and environment name are not exposed.
8. **Given** the environment is `local` or `dev`, **When** a request hits `GET /api/v2/runtime`, **Then** the full response (including `sse_url` and `environment`) is returned.

### User Story 3 — Missing Auth on Refresh Status (Priority: P0)

`GET /api/v2/configurations/{id}/refresh/status` has NO authentication check. Any caller can query refresh status for any configuration by guessing IDs.

**Why this priority**: Missing `_require_user_id()` call is a bug, not a design choice.

**Acceptance Scenarios**:

9. **Given** no Bearer token is provided, **When** a request hits `GET /api/v2/configurations/{id}/refresh/status`, **Then** the response is HTTP 401.
10. **Given** a valid Bearer token for user A, **When** user A requests refresh status for user B's configuration, **Then** the response is HTTP 403 (ownership check).

### User Story 4 — Session Validation Enforced on Data Endpoints (Priority: P1)

Four handler.py endpoints use `validate_session=False`, but the parameter is **unused** in `_get_user_id_from_event()` — session validity is never checked. Expired or revoked sessions can still access data.

**Affected endpoints**: `/api/v2/metrics`, `/api/v2/sentiment`, `/api/v2/trends`, `/api/v2/articles` (handler.py lines 431, 483, 547, 656).

**Why this priority**: Revoked sessions should not access data. The code was designed for validation but never wired.

**Acceptance Scenarios**:

11. **Given** a revoked session token, **When** a request hits `GET /api/v2/metrics`, **Then** the response is HTTP 401 or 403.
12. **Given** a valid session token, **When** a request hits any of the 4 endpoints, **Then** existing behavior is preserved.

### Edge Cases

- What if a developer needs the admin dashboard in preprod for debugging? They can use the local dev server or temporarily set an env var override. The default must be locked down.
- What if the `/api` documentation index is also publicly accessible? It should return 404 in prod (it exposes endpoint inventory).
- What if removing `validate_session=False` causes test failures? Tests must be updated to use valid session tokens, not bare UUID headers.
- What if the `_get_user_id_from_event()` function is used elsewhere with intentional False? Only the 4 handler.py endpoints are affected; the router_v2.py `refresh_session()` use at line 718 is deliberate (CSRF middleware provides its own validation).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Routes `GET /`, `GET /chaos`, `GET /static/*`, `GET /api`, and `GET /favicon.ico` MUST return HTTP 404 when the environment is NOT explicitly `local`, `dev`, or `test`. This is a **fail-closed** design: if `ENVIRONMENT` is unset, empty, or any unrecognized value, the dashboard is locked down. The deploy script only hits `/health` (verified: deploy.yml line 1165), not `/`.
- **FR-002**: Routes MUST serve content ONLY when `ENVIRONMENT` is explicitly one of `local`, `dev`, `test`.
- **FR-003**: `GET /health` MUST return only `{"status":"healthy"}` with no `table` or `environment` keys when NOT in local/dev/test. In dev, the full response is acceptable. Deploy smoke tests verified: deploy.yml:1167 checks valid JSON only, line 2033 greps for `"status"` key only — neither parses `table` or `environment`.
- **FR-004**: The lockdown MUST be implemented at the application level (environment check in the route handler), not infrastructure level.
- **FR-005**: A Playwright or integration test MUST verify that admin routes return 404 on the deployed preprod environment.
- **FR-006**: Existing API routes (`/api/v2/*`) MUST NOT be affected (except those explicitly fixed below).
- **FR-007**: `GET /api/v2/runtime` MUST omit `sse_url` and `environment` when NOT in local/dev/test. Return `{"sse_url": null, "environment": "production"}` (generic label, not actual env name).
- **FR-008**: `GET /api/v2/configurations/{id}/refresh/status` MUST require authentication via `_require_user_id()`. Return 401 if no valid token.
- **FR-009**: The `_get_user_id_from_event()` function in handler.py MUST implement session validation when `validate_session=True`. The 4 data endpoints (metrics, sentiment, trends, articles) MUST switch from `validate_session=False` to `validate_session=True`.
- **FR-010**: The router_v2.py `refresh_session()` call at line 718 MUST remain `validate_session=False` (CSRF middleware provides its own validation layer).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `curl https://<function-url>/` returns HTTP 404 on preprod.
- **SC-002**: `curl https://<function-url>/chaos` returns HTTP 404 on preprod.
- **SC-003**: `curl https://<function-url>/health` returns `{"status":"healthy"}` with no `table`/`environment` keys.
- **SC-004**: All existing API tests (`/api/v2/*`) continue to pass.
- **SC-005**: Local dev dashboard (`python scripts/run-local-api.py`) still serves the admin dashboard.
- **SC-006**: `curl https://<function-url>/api/v2/runtime` returns `{"sse_url": null, "environment": "production"}` on preprod.
- **SC-007**: `curl https://<function-url>/api/v2/configurations/any-id/refresh/status` returns HTTP 401 without a Bearer token.
- **SC-008**: Revoked session token on `/api/v2/metrics` returns HTTP 401 or 403.

## Assumptions

- The `ENVIRONMENT` env var is correctly set on all Lambda deployments (verified: it's in Terraform).
- No external system depends on the admin dashboard routes in preprod/prod.
- The `/health` endpoint is used by deploy scripts for smoke testing — the simplified response (`{"status":"ok"}`) must still return HTTP 200.
