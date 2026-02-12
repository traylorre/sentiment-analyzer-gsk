# Feature Specification: Security Headers and Auth Error Codes

**Feature Branch**: `1190-security-headers-error-codes`
**Created**: 2026-01-10
**Status**: Draft
**Input**: User description: "A22-A23: (1) Add security response headers middleware (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS, CSP). (2) Implement AUTH_013-AUTH_018 error codes for identity flows with no role leak in messages."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Security Headers Protection (Priority: P1)

All API responses include security headers that protect against common web vulnerabilities (XSS, clickjacking, MIME sniffing, protocol downgrade attacks).

**Why this priority**: Security headers are a foundational defense-in-depth measure required by OWASP. Without them, the application is vulnerable to client-side attacks even if token handling is secure.

**Independent Test**: Can be verified by making any API request and inspecting response headers. Delivers immediate security hardening.

**Acceptance Scenarios**:

1. **Given** any API endpoint, **When** a request is made, **Then** the response includes `X-Content-Type-Options: nosniff`
2. **Given** any API endpoint, **When** a request is made, **Then** the response includes `X-Frame-Options: DENY`
3. **Given** any API endpoint, **When** a request is made, **Then** the response includes a restrictive `Content-Security-Policy`
4. **Given** any API endpoint, **When** a request is made, **Then** the response includes `Referrer-Policy: strict-origin-when-cross-origin`
5. **Given** any API endpoint, **When** a request is made, **Then** the response includes `Permissions-Policy` denying sensitive capabilities

---

### User Story 2 - HSTS Enforcement via CDN (Priority: P1)

All responses served through CloudFront enforce HTTPS via Strict-Transport-Security header, preventing protocol downgrade attacks.

**Why this priority**: HSTS must be set at the CDN layer to ensure all traffic is secured, including initial requests before the application is reached.

**Independent Test**: Can be verified by checking CloudFront response headers. Delivers transport layer security.

**Acceptance Scenarios**:

1. **Given** a request through CloudFront, **When** response is returned, **Then** `Strict-Transport-Security` header is present with max-age of at least 1 year
2. **Given** the HSTS header, **When** parsed, **Then** it includes `includeSubDomains` directive
3. **Given** the HSTS header, **When** parsed, **Then** it includes `preload` directive

---

### User Story 3 - Identity Flow Error Codes (Priority: P1)

Users receive clear, actionable error messages for identity-related failures without exposing internal system details or role information.

**Why this priority**: Clear error codes enable proper client-side error handling and improve user experience while preventing information leakage that could aid attackers.

**Independent Test**: Can be verified by triggering each error condition and checking response format. Delivers better UX and security.

**Acceptance Scenarios**:

1. **Given** a user whose password was changed, **When** they use an old session, **Then** they receive AUTH_013 with message "Credentials have been changed"
2. **Given** a user who exceeds the session limit, **When** evicted by a new login, **Then** they receive AUTH_014 with message "Session limit exceeded"
3. **Given** an OAuth request with unknown provider, **When** processed, **Then** they receive AUTH_015 with message "Unknown OAuth provider"
4. **Given** an OAuth callback with mismatched provider, **When** state is validated, **Then** they receive AUTH_016 with message "OAuth provider mismatch"
5. **Given** a password that doesn't meet requirements, **When** submitted, **Then** they receive AUTH_017 with message "Password requirements not met"
6. **Given** a token with wrong environment audience, **When** validated, **Then** they receive AUTH_018 with message "Token audience invalid"

---

### User Story 4 - Client Error Handler Integration (Priority: P2)

The frontend correctly handles each new error code with appropriate user actions (clear tokens, show messages, redirect).

**Why this priority**: Backend error codes are only useful if the frontend handles them correctly. This completes the error flow.

**Independent Test**: Can be verified by mocking each error code response and checking frontend behavior.

**Acceptance Scenarios**:

1. **Given** AUTH_013 response, **When** handled by frontend, **Then** tokens are cleared and user sees "Your password was changed" message
2. **Given** AUTH_014 response, **When** handled by frontend, **Then** tokens are cleared and user sees "Signed in on another device" message
3. **Given** AUTH_015 response, **When** handled by frontend, **Then** user sees list of supported providers
4. **Given** AUTH_016 response, **When** handled by frontend, **Then** OAuth flow restarts automatically
5. **Given** AUTH_017 response, **When** handled by frontend, **Then** password requirements are displayed
6. **Given** AUTH_018 response, **When** handled by frontend, **Then** tokens are cleared silently

---

### Edge Cases

- What happens when CSP blocks a legitimate resource? CSP must allow Cognito endpoints for OAuth.
- What happens when HSTS preload is enabled but domain isn't on preload list? Still provides protection via max-age.
- What happens when error code is unknown to frontend? Falls back to generic error handler.
- What happens when multiple errors occur simultaneously? Most severe error (lowest HTTP status) is returned.

## Requirements _(mandatory)_

### Functional Requirements

**Security Headers (A22)**:
- **FR-001**: System MUST include `X-Content-Type-Options: nosniff` on all API responses
- **FR-002**: System MUST include `X-Frame-Options: DENY` on all API responses
- **FR-003**: System MUST include `Content-Security-Policy` that allows only self-origin scripts and styles
- **FR-004**: System MUST include `Referrer-Policy: strict-origin-when-cross-origin` on all responses
- **FR-005**: System MUST include `Permissions-Policy` denying geolocation, microphone, and camera
- **FR-006**: System MUST configure CloudFront to add `Strict-Transport-Security` with 1-year max-age
- **FR-007**: CSP MUST allow connections to Cognito identity provider endpoints for OAuth flows

**Error Codes (A23)**:
- **FR-008**: System MUST define AUTH_013 (401) for "Credentials have been changed" scenario
- **FR-009**: System MUST define AUTH_014 (401) for "Session limit exceeded" scenario
- **FR-010**: System MUST define AUTH_015 (400) for "Unknown OAuth provider" scenario
- **FR-011**: System MUST define AUTH_016 (400) for "OAuth provider mismatch" scenario
- **FR-012**: System MUST define AUTH_017 (400) for "Password requirements not met" scenario
- **FR-013**: System MUST define AUTH_018 (401) for "Token audience invalid" scenario
- **FR-014**: Error messages MUST NOT leak role information or internal system details
- **FR-015**: Frontend MUST handle each error code with appropriate user action

### Key Entities

- **SecurityHeaders**: Configuration object mapping header names to values
- **AuthError**: Error definition with code, message, HTTP status, and client action guidance
- **ErrorCodeRegistry**: Central registry of AUTH_001-AUTH_018 error definitions

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of API responses include all 5 required security headers
- **SC-002**: Security scanner (OWASP ZAP or similar) reports no missing security headers
- **SC-003**: CloudFront HSTS header has max-age >= 31536000 (1 year)
- **SC-004**: All 6 new error codes (AUTH_013-AUTH_018) are defined and documented
- **SC-005**: No error response contains role names, internal paths, or stack traces
- **SC-006**: Frontend handles all error codes without crashing or showing raw JSON

## Assumptions

- CloudFront is already configured and serves the application (header policy can be attached)
- Existing error code pattern (AUTH_001-AUTH_012) is established and should be extended
- Frontend error handling infrastructure exists and can be extended
- CSP allows 'unsafe-inline' for styles (common for CSS-in-JS frameworks)

## Dependencies

- Spec-v2.md section on security headers (referenced as v2.6 Phase 1)
- Existing AuthError class and error code registry
- CloudFront response headers policy (Terraform)

## Out of Scope

- X-XSS-Protection header (deprecated in modern browsers, CSP supersedes it)
- Subresource Integrity (SRI) for third-party scripts (no third-party scripts in use)
- Feature-Policy (superseded by Permissions-Policy)
- Report-URI / report-to for CSP violation reporting (future enhancement)
