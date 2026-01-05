# Feature Specification: Random Magic Link Tokens

**Feature Branch**: `1127-random-magic-tokens`
**Created**: 2026-01-04
**Status**: Draft
**Input**: Phase 0 C1/D2: Replace HMAC-based magic link secret with cryptographically secure random tokens. Delete hardcoded fallback secret. CVSS 9.1 - BLOCKING PRODUCTION.
**Security Priority**: CRITICAL (Phase 0 - Must complete before any other feature work)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Secure Magic Link Request (Priority: P1)

A user requests a magic link for passwordless authentication. The system generates a cryptographically secure random token that cannot be predicted or forged, even if an attacker knows the system's internal logic.

**Why this priority**: This is the core security fix. The current HMAC-based approach allows token prediction if the secret is compromised (or uses the hardcoded fallback). Random tokens are cryptographically unpredictable by design.

**Independent Test**: Can be fully tested by requesting a magic link and verifying the token meets randomness requirements (256-bit entropy, unpredictable across requests).

**Acceptance Scenarios**:

1. **Given** a user requests a magic link, **When** the system generates a token, **Then** the token MUST be 256 bits of cryptographic randomness (43 URL-safe characters).
2. **Given** multiple magic link requests, **When** tokens are generated, **Then** each token MUST be statistically independent (no predictable pattern).
3. **Given** a magic link token, **When** an attacker attempts to forge a valid token, **Then** the probability of success MUST be less than 1 in 2^256.

---

### User Story 2 - Hardcoded Secret Elimination (Priority: P1)

The system MUST NOT contain any hardcoded fallback secrets for magic link generation. If configuration is missing, the system must fail securely rather than using an insecure default.

**Why this priority**: Equal priority to P1 because hardcoded secrets (CVSS 9.1) are the root cause of the vulnerability. The current fallback `'default-dev-secret-change-in-prod'` allows complete token forgery.

**Independent Test**: Can be tested by searching the codebase for hardcoded secrets and verifying the system fails when proper configuration is absent.

**Acceptance Scenarios**:

1. **Given** the magic link secret configuration is missing, **When** the system attempts to generate a token, **Then** the system MUST fail with a clear error (not silently use a fallback).
2. **Given** the codebase, **When** security scanning tools analyze the code, **Then** no hardcoded secrets related to magic link generation MUST be found.
3. **Given** a deployment without proper secret configuration, **When** a user requests a magic link, **Then** the request MUST fail with a 500 error and log the misconfiguration (no token generated).

---

### User Story 3 - Magic Link Verification Unchanged (Priority: P2)

Users clicking valid magic links continue to authenticate successfully. The verification process remains functionally identical from the user's perspective.

**Why this priority**: Lower priority because this is about maintaining existing functionality, not the core security fix. However, breaking verification would block users entirely.

**Independent Test**: Can be tested by requesting a magic link, clicking it within the validity window, and verifying successful authentication.

**Acceptance Scenarios**:

1. **Given** a user receives a valid magic link, **When** they click it within 1 hour, **Then** they MUST be authenticated successfully.
2. **Given** a user receives a valid magic link, **When** they click it after 1 hour, **Then** authentication MUST fail with "link expired" message.
3. **Given** a user clicks a magic link, **When** the link has already been used, **Then** authentication MUST fail with "link already used" message.

---

### Edge Cases

- What happens when the random number generator fails? System MUST fail securely (500 error, no token generated).
- What happens when token storage fails after generation? System MUST NOT send the magic link email if storage failed.
- What happens during migration (old HMAC tokens still in database)? Existing tokens MUST continue to work until they expire naturally (backward compatibility).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST generate magic link tokens using a cryptographically secure random number generator producing 256 bits of entropy.
- **FR-002**: System MUST NOT contain any hardcoded secret values for magic link token generation or verification.
- **FR-003**: System MUST fail with a clear, logged error if cryptographic operations fail (fail-secure, not fail-open).
- **FR-004**: System MUST maintain backward compatibility with existing unexpired magic link tokens during migration.
- **FR-005**: System MUST store tokens in a way that allows verification without reconstructing them from secrets.
- **FR-006**: System MUST log security-relevant events (token generation, verification attempts, failures) without logging the tokens themselves.
- **FR-007**: System MUST reject any attempt to use a token more than once (one-time use enforcement).

### Key Entities

- **Magic Link Token**: A cryptographically random string (256-bit, URL-safe encoded) used for passwordless authentication. Stored with: user association, creation timestamp, expiration timestamp, used flag.
- **Token Request**: Records of magic link generation attempts. Includes: requesting email, IP address, timestamp, success/failure status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero hardcoded secrets in the codebase related to magic link generation (verified by automated security scanning).
- **SC-002**: Token entropy MUST be 256 bits or greater (verified by statistical randomness tests on sample tokens).
- **SC-003**: System continues to successfully authenticate users via magic links (no regression in success rate).
- **SC-004**: Security scanners (secret detection tools) report zero findings for magic link-related code paths.
- **SC-005**: Failed cryptographic operations result in 500 errors with appropriate logging (verified by fault injection testing).

## Assumptions

- The existing token storage mechanism (database) does not require changes - only the token generation method changes.
- Magic link expiration (1 hour) and one-time-use behavior remain unchanged.
- The system has access to a cryptographically secure random number generator (standard in all supported deployment environments).
- Existing unexpired tokens using the old method will naturally expire within 1 hour, so no explicit migration is needed.

## Out of Scope

- Atomic token consumption (covered in separate Phase 0 fix C3)
- Rate limiting for magic link requests (covered in Phase 3)
- Changes to magic link email templates or delivery mechanism
- Changes to user-facing error messages beyond what's needed for security
