# Feature Specification: Remove Hardcoded MAGIC_LINK_SECRET

**Feature Branch**: `1164-remove-magic-link-hardcoded-secret`
**Created**: 2026-01-06
**Status**: Draft
**Input**: Phase 0 C1 Security Fix - Remove hardcoded secret fallback

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Remove Hardcoded Secret Exposure (Priority: P1)

As a security engineer, I need the hardcoded MAGIC_LINK_SECRET fallback removed from the codebase so that production systems cannot accidentally use a known default value, which would be a critical security vulnerability.

**Why this priority**: This is a security blocker. Hardcoded secrets in source code are OWASP Top 10 violations and can lead to complete authentication bypass if the default is used in production.

**Independent Test**: Can be verified by searching the codebase for the hardcoded string and confirming it no longer exists. Additionally, the system should fail clearly at startup if the environment variable is not set.

**Acceptance Scenarios**:

1. **Given** the auth module starts without MAGIC_LINK_SECRET env var, **When** the application loads, **Then** a clear error is raised immediately (not at first token request).
2. **Given** the hardcoded fallback "default-dev-secret-change-in-prod" exists in code, **When** this feature is complete, **Then** the string does not appear anywhere in the codebase.
3. **Given** MAGIC_LINK_SECRET is set via environment variable, **When** the auth module loads, **Then** the system operates normally.

---

### User Story 2 - Remove Dead Signature Verification Code (Priority: P2)

As a developer, I want dead code removed from the codebase so that future maintainers are not confused by orphaned functions that appear security-critical but are never called.

**Why this priority**: Code hygiene and reducing attack surface. The signature verification function exists but is never called, creating confusion about whether it should be called.

**Independent Test**: Can be verified by removing the function and ensuring all tests pass.

**Acceptance Scenarios**:

1. **Given** the `_verify_magic_link_signature()` function exists but is never called, **When** this feature is complete, **Then** the function is removed.
2. **Given** tests that reference signature verification, **When** they are updated, **Then** they focus on atomic token consumption (the actual security mechanism).

---

### User Story 3 - Update Tests to Remove Secret Dependencies (Priority: P3)

As a test engineer, I need tests updated to not rely on hardcoded secrets so that the test suite reflects the production security posture.

**Why this priority**: Tests should validate actual security mechanisms, not deprecated ones.

**Independent Test**: All tests pass with proper environment variable setup via pytest fixtures.

**Acceptance Scenarios**:

1. **Given** tests that set MAGIC_LINK_SECRET to test values, **When** tests run, **Then** they use environment variables properly set by fixtures.
2. **Given** test helpers that generate HMAC signatures, **When** this feature is complete, **Then** they align with actual production behavior.

---

### Edge Cases

- What happens if MAGIC_LINK_SECRET is empty string? → Treat as unset, raise error.
- What happens to existing tokens in database with signatures? → They continue to work because verification uses atomic DynamoDB lookup, not signature validation.
- What happens in local development without env var? → Clear error message guides developer to set the variable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST NOT contain hardcoded secret values in source code.
- **FR-002**: System MUST raise a clear error at module load time if MAGIC_LINK_SECRET environment variable is not set or is empty.
- **FR-003**: System MUST remove the orphaned `_verify_magic_link_signature()` function since it is never called.
- **FR-004**: System MUST update tests to use proper environment variable fixtures instead of relying on hardcoded fallbacks.
- **FR-005**: System MUST NOT break existing magic link flows - token generation and verification via atomic DynamoDB operations must continue working.

### Key Entities

- **MAGIC_LINK_SECRET**: Environment variable containing the HMAC signing key for magic link tokens. Required for token generation.
- **MagicLinkToken**: Database entity storing token data including signature (still generated but not verified).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero instances of hardcoded secret strings in the codebase (verified by grep).
- **SC-002**: Application fails fast at startup without required secrets (not at first use).
- **SC-003**: All existing tests pass after changes.
- **SC-004**: Magic link authentication flows continue to work in production.
- **SC-005**: Code reduction: removal of at least one orphaned function.

## Assumptions

- The signature verification function is confirmed to be dead code (never called).
- Atomic token consumption via DynamoDB ConditionExpression is the actual security mechanism.
- Existing tokens in the database will continue to work since verification doesn't check signatures.
- The MAGIC_LINK_SECRET is still needed for signature generation (stored in tokens for future audit/compatibility).

## Dependencies

- None - this is a standalone security cleanup.

## Canonical Source

- specs/1126-auth-httponly-migration/implementation-gaps.md (Phase 0 C1)
- OWASP Secure Coding Guidelines for Secrets Management
