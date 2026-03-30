# Feature Specification: CORS Wildcard Origin Fix

**Feature Branch**: `1268-cors-wildcard-fix`
**Created**: 2026-03-28
**Status**: Draft
**Input**: User description: "Fix API Gateway OPTIONS responses that return Access-Control-Allow-Origin: '*' combined with Access-Control-Allow-Credentials: 'true', which violates CORS spec (Fetch Standard section 3.2.5) and causes silent browser rejection of all credentialed requests"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Authenticated Dashboard User Makes API Calls (Priority: P1)

A logged-in user on the customer dashboard (Amplify/Next.js frontend) performs actions that trigger API calls with credentials (httpOnly refresh token cookies). Currently, the browser silently drops every response because the OPTIONS preflight returns `Access-Control-Allow-Origin: *` alongside `Access-Control-Allow-Credentials: true`. After this fix, the browser accepts the CORS preflight and the user sees data load correctly.

**Why this priority**: This is the core bug. Without this fix, every credentialed API call from the frontend silently fails. The dashboard appears empty or broken with no error visible to the user.

**Independent Test**: Can be verified by making a credentialed fetch from an allowed origin and confirming the response includes the echoed origin header (not a wildcard).

**Acceptance Scenarios**:

1. **Given** a user on the Amplify frontend at an allowed origin, **When** they make a credentialed API call that triggers a CORS preflight, **Then** the OPTIONS response echoes their specific origin in `Access-Control-Allow-Origin` and includes `Access-Control-Allow-Credentials: true`.
2. **Given** a user on the Amplify frontend, **When** the preflight succeeds and the actual request returns data, **Then** the browser does not block the response and the dashboard renders the data.
3. **Given** a user on the Amplify frontend, **When** the API returns a 401 or 403 error, **Then** the error response also includes the correct CORS headers (specific origin, not wildcard) so the browser exposes the error body to JavaScript.

---

### User Story 2 - Local Developer Testing Against API (Priority: P2)

A developer running the frontend locally at `http://localhost:3000` makes credentialed API calls to the preprod API Gateway. The CORS preflight must echo `http://localhost:3000` (not `*`) so the browser permits the response.

**Why this priority**: Developer workflow is critical for iteration speed. Localhost origins must be in the allowlist for non-production environments.

**Independent Test**: Can be verified by running the frontend locally and confirming API calls succeed without CORS console errors.

**Acceptance Scenarios**:

1. **Given** a developer running the frontend at `http://localhost:3000`, **When** they make a credentialed API call to the preprod API, **Then** the OPTIONS response echoes `http://localhost:3000` in `Access-Control-Allow-Origin`.
2. **Given** a developer running at `http://localhost:8080` (alternative port), **When** they make a credentialed API call, **Then** the response echoes `http://localhost:8080` if it is in the configured allowlist.

---

### User Story 3 - Unauthorized Origin Is Rejected (Priority: P2)

A request from an origin not in the allowlist (e.g., a malicious site or unauthorized domain) must NOT receive permissive CORS headers. The browser should block the cross-origin response, preventing credential theft via CSRF-like attacks.

**Why this priority**: Security parity with P1. Allowing arbitrary origins with credentials enabled is a security vulnerability (credential leakage to attacker-controlled domains).

**Independent Test**: Can be verified by sending an OPTIONS request with an Origin header not in the allowlist and confirming the response does NOT include `Access-Control-Allow-Origin`.

**Acceptance Scenarios**:

1. **Given** a request from `https://evil.example.com`, **When** the CORS preflight is received, **Then** the response does NOT include `Access-Control-Allow-Origin: https://evil.example.com`.
2. **Given** a request with no Origin header, **When** the CORS preflight is received, **Then** the response does NOT include `Access-Control-Allow-Origin: *`.

---

### User Story 4 - Infrastructure Consistency Across All Response Types (Priority: P3)

The CORS origin handling must be consistent across all API Gateway response types: OPTIONS preflight responses, gateway error responses (401, 403), and Lambda proxy responses. Currently, gateway error responses correctly use the request origin, but OPTIONS responses use a wildcard. After this fix, all response types use the same origin-echoing behavior.

**Why this priority**: Inconsistency between response types creates intermittent failures that are extremely difficult to debug. A unified approach prevents future regressions.

**Independent Test**: Can be verified by comparing CORS headers across OPTIONS, 200, 401, and 403 responses and confirming they all echo the same specific origin.

**Acceptance Scenarios**:

1. **Given** a request from an allowed origin, **When** any response type is returned (200, 401, 403, OPTIONS), **Then** all responses include `Access-Control-Allow-Origin` set to the requesting origin (not `*`).
2. **Given** the infrastructure configuration, **When** an operator reviews CORS settings, **Then** there is a single source of truth for the origin-echoing pattern (no wildcard fallbacks anywhere).

---

### Edge Cases

- What happens when a request arrives with no `Origin` header? API Gateway's `method.request.header.Origin` will be empty. The response should omit `Access-Control-Allow-Origin` entirely (safe default).
- What happens when `cors_allowed_origins` is empty (dev environment)? The system should fall back to localhost origins for non-production environments, matching existing behavior in Lambda Function URL CORS and SSE CORS configuration.
- What happens if the requesting origin matches the allowlist but with a different scheme (http vs https)? Origins are compared as exact strings per the CORS spec. `http://example.com` and `https://example.com` are different origins.
- What happens during deployment when this change applies? The API Gateway deployment must be triggered by the configuration change. Existing deployment trigger logic (based on resource IDs) should handle this.
- What happens to response caching? The `Vary: Origin` header should be present to ensure CDN/browser caches don't serve a cached response with one origin to a request from a different origin.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The OPTIONS preflight response MUST set `Access-Control-Allow-Origin` to the exact requesting origin when that origin appears in the configured allowlist.
- **FR-002**: The OPTIONS preflight response MUST NOT set `Access-Control-Allow-Origin` to `*` (wildcard) under any circumstances when `Access-Control-Allow-Credentials` is `true`.
- **FR-003**: When the requesting origin is NOT in the allowlist, the response MUST omit the `Access-Control-Allow-Origin` header (or return a non-matching value), causing the browser to block the response.
- **FR-004**: The API Gateway module MUST accept an allowlist of permitted origins as configuration input.
- **FR-005**: The origin-echoing behavior in OPTIONS responses MUST be consistent with the existing behavior in gateway error responses (401, 403), which already use `method.request.header.origin`.
- **FR-006**: All existing CORS headers (`Access-Control-Allow-Headers`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Credentials`) MUST remain unchanged.
- **FR-007**: The `Vary: Origin` header SHOULD be included in responses to prevent cache poisoning where a cached response for one origin is served to another.
- **FR-008**: The system MUST NOT permit wildcard (`*`) values in the origin allowlist configuration, enforced by input validation.

### Key Entities

- **Origin Allowlist**: A list of exact origin strings (scheme + host + port) permitted for cross-origin credentialed requests. Configured per environment via tfvars.
- **CORS Headers Local**: The configuration value that defines the set of CORS response headers applied to all OPTIONS integration responses in the API Gateway module.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Credentialed API calls from the customer dashboard succeed without CORS errors for 100% of requests from allowed origins.
- **SC-002**: No `Access-Control-Allow-Origin: *` appears in any API Gateway response when `Access-Control-Allow-Credentials: true` is present.
- **SC-003**: Requests from origins not in the allowlist are blocked by the browser (CORS rejection), with 0% of unauthorized origins receiving permissive headers.
- **SC-004**: All four test layers pass: unit tests (configuration validation), integration tests (header verification), E2E tests (deployed API behavior), and browser-level tests (dashboard functionality).
- **SC-005**: The fix introduces zero downtime during deployment (redeployment is atomic).

## Assumptions

- The request header reference (`method.request.header.Origin`) is available in mock integration response mappings for OPTIONS methods. This is confirmed by the existing gateway error responses that already use `method.request.header.origin`.
- The `cors_allowed_origins` variable already exists at the root module level with wildcard validation. It needs to be passed through to the API Gateway child module.
- The frontend exclusively uses `credentials: 'include'` for all API calls (confirmed in `client.ts` line 148), meaning the wildcard-with-credentials bug affects every API call.

## Open Questions

- **OQ-1**: Can API Gateway MOCK integration responses perform origin validation (check if the Origin header matches an allowlist), or can they only echo the header verbatim? If only echo, the allowlist validation would need to happen at a different layer (e.g., Lambda middleware, or by accepting the echo-only approach since the browser enforces same-origin policy anyway). This needs investigation during planning.
- **OQ-2**: For Playwright E2E CORS testing specifically: Playwright runs in a real browser but typically against `localhost`. Testing true cross-origin CORS behavior (where the page origin differs from the API origin) may require specific test infrastructure setup. This should be flagged as an open question for test feasibility.

## Adversarial Review #1

**Reviewer perspective**: Security penetration tester, infrastructure reliability engineer, test architect.

### Finding AR1-01: CRITICAL - API Gateway MOCK Integrations Cannot Validate Origin Against Allowlist

**Attack vector**: OQ-1 from the spec is actually a CRITICAL feasibility issue, not just an open question. API Gateway integration responses for MOCK integrations can reference `method.request.header.Origin` to echo the request origin, but they CANNOT perform conditional logic (e.g., "only echo if origin is in allowlist"). This means any origin sent in the `Origin` header will be echoed back in the OPTIONS response.

**Risk**: An attacker at `https://evil.example.com` sends a credentialed request. The MOCK integration echoes `https://evil.example.com` in `Access-Control-Allow-Origin` with `Access-Control-Allow-Credentials: true`. The browser allows the cross-origin credentialed response. This is an open redirect for credentials.

**Resolution**: This is mitigated at three layers:
1. **Gateway Responses (401/403)** already echo origin, but these are error responses the attacker cannot exploit for data exfiltration since they contain no user data.
2. **Lambda proxy responses** (200 success paths) set CORS headers in application code (`security_headers.py` middleware), which DOES validate against the `CORS_ORIGINS` environment variable. The attacker would get a valid OPTIONS preflight but the actual data response would be blocked by the Lambda's CORS validation.
3. **The CORS spec itself**: The OPTIONS preflight only authorizes the browser to *send* the actual request. The actual response (from Lambda, not MOCK) still needs its own `Access-Control-Allow-Origin` header. If Lambda rejects the origin, the browser blocks the response body.

**Verdict**: ACCEPTABLE RISK. The echo-only approach for OPTIONS is the standard AWS pattern. The actual data protection comes from Lambda-level origin validation. FR-003 should be AMENDED to clarify that origin validation for data responses happens at the application layer, not the OPTIONS preflight layer.

**Spec update**: FR-003 amended below.

### Finding AR1-02: HIGH - Missing Requirement for Lambda-Level Origin Validation Consistency

**Attack vector**: The spec focuses entirely on the API Gateway OPTIONS response but ignores the Lambda middleware that sets CORS headers on actual (non-OPTIONS) responses. If the Lambda middleware uses a different origin list than the API Gateway, there's a gap.

**Risk**: Split-brain configuration where OPTIONS says "yes" but the actual response says "no" (or vice versa), causing confusing intermittent failures.

**Resolution**: The root module already passes `CORS_ORIGINS = join(",", var.cors_allowed_origins)` as a Lambda environment variable (main.tf line 416). The Lambda middleware (`security_headers.py`) validates against this. Both will derive from the same `cors_allowed_origins` tfvars variable. Add an explicit requirement.

**Spec update**: Added FR-009 below.

### Finding AR1-03: HIGH - Vary Header Not Just SHOULD But MUST

**Attack vector**: Without `Vary: Origin`, a CDN or browser HTTP cache could serve a response intended for `https://allowed-a.com` to a request from `https://allowed-b.com`. If both are in the allowlist but the cache returns the wrong origin, CORS fails.

**Risk**: Intermittent CORS failures after CDN caching, extremely difficult to diagnose.

**Resolution**: Upgrade FR-007 from SHOULD to MUST. API Gateway responses that vary by origin MUST include `Vary: Origin`.

**Spec update**: FR-007 amended below.

### Finding AR1-04: MEDIUM - Edge Case for Empty Origin Header Underspecified

**Attack vector**: When `method.request.header.Origin` is empty or missing, API Gateway echoes an empty string. This means `Access-Control-Allow-Origin: ""` which is technically a non-matching origin (browser rejects). However, same-origin requests from the API Gateway's own domain don't send an `Origin` header and don't need CORS. The edge case is that non-browser clients (like curl or Postman) might not send `Origin`.

**Risk**: Low. Non-browser clients don't enforce CORS. This is a non-issue in practice.

**Resolution**: No spec change needed. The empty-echo behavior is safe. Document in assumptions.

### Finding AR1-05: MEDIUM - Playwright CORS Testing Feasibility

**Attack vector**: OQ-2 is valid. Playwright cannot easily test CORS because:
1. Playwright typically navigates to `localhost:3000` which makes same-origin requests to `localhost:3000`'s dev server proxy.
2. To test true CORS, the Playwright page must be served from one origin and make requests to a different origin.
3. The existing Playwright tests likely use a proxy configuration that avoids CORS entirely.

**Resolution**: Mark Playwright CORS testing as DEFERRED. The three other test layers (unit, integration, E2E via curl/httpie) provide sufficient coverage. Playwright tests should verify the dashboard *works* (which implicitly validates CORS), not test CORS header mechanics directly.

**Spec update**: SC-004 amended to note Playwright tests verify dashboard functionality (implicit CORS validation), not direct CORS header assertions.

### Amended Requirements

**FR-003 (amended)**: For OPTIONS preflight responses, the system echoes the requesting origin header verbatim (standard AWS API Gateway pattern). Origin allowlist validation for data responses is enforced at the application layer (Lambda middleware), not the OPTIONS preflight layer. The browser's CORS enforcement ensures that even if OPTIONS succeeds, unauthorized origins cannot read data responses.

**FR-007 (amended from SHOULD to MUST)**: The `Vary: Origin` header MUST be included in all responses that vary by origin to prevent cache poisoning.

**FR-009 (new)**: The application layer (Lambda middleware) and the infrastructure layer (API Gateway OPTIONS) MUST both derive their allowed origin lists from the same configuration source, ensuring no split-brain origin validation.

### Summary

| Finding  | Severity | Status   |
|----------|----------|----------|
| AR1-01   | CRITICAL | RESOLVED - echo-only is standard; Lambda validates actual responses |
| AR1-02   | HIGH     | RESOLVED - added FR-009 for config consistency |
| AR1-03   | HIGH     | RESOLVED - FR-007 upgraded to MUST |
| AR1-04   | MEDIUM   | RESOLVED - empty origin is safe (non-matching) |
| AR1-05   | MEDIUM   | RESOLVED - Playwright tests verify functionality, not headers |

**Verdict**: All findings resolved. Spec is ready for planning.

## Clarifications

### Session 2026-03-28

No critical ambiguities detected. All 10 coverage taxonomy categories assessed as Clear:
- OQ-1 (MOCK integration validation) resolved by AR1-01 (echo-only is standard, Lambda validates data responses)
- OQ-2 (Playwright CORS testing) resolved by AR1-05 (deferred to implicit validation via dashboard functionality tests)
- FR-003 amended, FR-007 upgraded, FR-009 added during adversarial review

Spec is ready for `/speckit.plan` (already completed) and `/speckit.tasks`.
