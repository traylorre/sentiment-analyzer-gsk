# Feature Specification: JWT Audience and Not-Before Claim Validation

**Feature Branch**: `1147-jwt-aud-nbf-validation`
**Created**: 2026-01-05
**Status**: Draft
**Input**: User description: "D3: Add aud (audience) and nbf (not-before) JWT claim validation to auth_middleware.py. CVSS 7.8. Currently only validates exp and iss. Without aud validation, tokens from other services can be replayed. Without nbf validation, pre-generated tokens work before they should. Location: src/lambdas/shared/middleware/auth_middleware.py lines 112-169."

## Problem Statement

The JWT validation in `auth_middleware.py` currently validates only `exp` (expiration) and `iss` (issuer) claims. This creates two critical security vulnerabilities (CVSS 7.8):

1. **Cross-Service Token Replay**: Without `aud` (audience) validation, a token generated for Service A can be accepted by Service B, enabling unauthorized access across services.

2. **Pre-Generated Token Attack**: Without `nbf` (not-before) validation, attackers can pre-generate tokens for future use before they should be valid, potentially bypassing time-based security controls.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reject Cross-Service Tokens (Priority: P1)

The system must reject JWT tokens that were issued for a different service or environment, preventing cross-service token replay attacks.

**Why this priority**: This is the highest severity vulnerability (cross-service attacks enable broad unauthorized access). Security-critical.

**Independent Test**: Can be fully tested by presenting a valid JWT with incorrect audience claim and verifying rejection with 401 response.

**Acceptance Scenarios**:

1. **Given** a valid JWT with `aud: "other-service-api"`, **When** the token is presented to the sentiment-analyzer API, **Then** the request is rejected with 401 Unauthorized
2. **Given** a valid JWT with `aud: "sentiment-analyzer-api-staging"`, **When** the token is presented to the production API, **Then** the request is rejected with 401 Unauthorized (environment isolation)
3. **Given** a valid JWT with `aud: "sentiment-analyzer-api"` matching the expected audience, **When** the token is presented to the API, **Then** the request proceeds to further validation

---

### User Story 2 - Reject Pre-Dated Tokens (Priority: P1)

The system must reject JWT tokens that have a `nbf` (not-before) timestamp in the future, preventing pre-generated token attacks.

**Why this priority**: Equal to P1 as this prevents time-based security bypass attacks. Security-critical.

**Independent Test**: Can be fully tested by presenting a JWT with `nbf` set 5 minutes in the future and verifying rejection.

**Acceptance Scenarios**:

1. **Given** a JWT with `nbf` timestamp 5 minutes in the future, **When** the token is presented now, **Then** the request is rejected with 401 Unauthorized
2. **Given** a JWT with `nbf` timestamp 30 seconds in the future, **When** the token is presented now, **Then** the request is rejected (within clock skew tolerance of 60 seconds, still fails as nbf > now)
3. **Given** a JWT with `nbf` timestamp 30 seconds in the past, **When** the token is presented now, **Then** the token passes nbf validation (within acceptable range)

---

### User Story 3 - Support Clock Skew Tolerance (Priority: P2)

The system must allow a reasonable clock skew tolerance to prevent authentication failures due to minor time differences between servers.

**Why this priority**: Prevents legitimate users from being locked out due to infrastructure clock drift, while maintaining security.

**Independent Test**: Can be tested by presenting a JWT with `nbf` exactly at current time on a server with slight clock offset.

**Acceptance Scenarios**:

1. **Given** a JWT with `nbf` timestamp exactly equal to current server time, **When** validated on a server with 30-second clock drift, **Then** the token is accepted (within 60-second leeway)
2. **Given** a JWT with `exp` timestamp 30 seconds in the past, **When** validated on a server with 30-second clock drift, **Then** the token is accepted (within 60-second leeway)
3. **Given** a JWT with timestamps more than 60 seconds beyond tolerance, **When** validated, **Then** the token is rejected

---

### Edge Cases

- What happens when `aud` claim is missing entirely from JWT? System MUST reject the token.
- What happens when `nbf` claim is missing entirely from JWT? System MUST reject the token (required claim).
- What happens when `aud` is an array containing the expected audience plus others? System MUST accept if expected audience is present.
- How does system handle tokens generated before this change (no aud/nbf)? System MUST reject them (breaking change by design for security).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST validate the `aud` (audience) claim on all incoming JWT tokens
- **FR-002**: System MUST validate the `nbf` (not-before) claim on all incoming JWT tokens
- **FR-003**: System MUST require `aud` and `nbf` claims to be present (reject tokens missing these claims)
- **FR-004**: System MUST apply a 60-second clock skew tolerance (leeway) for time-based validations
- **FR-005**: System MUST log audience mismatch events as security warnings for monitoring
- **FR-006**: System MUST use environment-specific audience values to prevent cross-environment token replay
- **FR-007**: System MUST return 401 Unauthorized for any token failing aud or nbf validation (no information leakage)
- **FR-008**: Token generation MUST include `aud` and `nbf` claims in all newly issued tokens

### Key Entities

- **JWT Token**: Authentication credential containing claims including `sub`, `exp`, `iat`, `iss`, `aud`, `nbf`
- **Audience (aud)**: Identifier for the intended recipient service of the token
- **Not-Before (nbf)**: Unix timestamp indicating when the token becomes valid

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of tokens with mismatched audience are rejected (verified via security test suite)
- **SC-002**: 100% of tokens with future nbf timestamps (beyond leeway) are rejected
- **SC-003**: Zero false rejections for legitimate tokens with timestamps within 60-second tolerance
- **SC-004**: Security audit passes with no cross-service token replay vulnerabilities
- **SC-005**: All existing authentication flows continue to work for legitimate users (no regression)

## Assumptions

- The expected audience value will be `sentiment-analyzer-api` (configurable via environment)
- Clock skew of up to 60 seconds is acceptable for the infrastructure
- This is a breaking change: tokens issued before this update will be rejected
- Token generation code already exists and will be updated to include the new claims
