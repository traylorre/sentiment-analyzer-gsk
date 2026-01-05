# Feature Specification: Guard Mock Token Generation

**Feature Branch**: `1128-guard-mock-tokens`
**Created**: 2026-01-05
**Status**: Implemented
**Input**: User description: "Phase 0 C2: Guard mock token generation with Lambda environment check. Prevents production Lambda from generating fake tokens."
**Context**: Part of Phase 0 Security Blocking for HTTPOnly cookie migration. Related spec: specs/1126-auth-httponly-migration/spec-v2.md

## Problem Statement

The `_generate_tokens()` function in `auth.py` (lines 1510-1529) generates mock tokens with predictable format (`mock_<type>_<user_id[:8]>`) without any environment validation. This function is called during:
- Magic link verification (`verify_magic_link()` at line 1465)
- OAuth callbacks (`handle_oauth_callback()` at line 1662)

**Security Risk**: If this code reaches production Lambda, authentication will succeed with fake tokens that:
1. Are predictable based on user ID
2. Bypass real Cognito token validation
3. Enable unauthorized access

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Production Lambda Rejects Mock Token Generation (Priority: P1)

When the application runs in AWS Lambda production environment, any attempt to generate mock tokens must immediately fail with a clear error, preventing fake credentials from being issued.

**Why this priority**: This is a critical security control. Mock tokens in production would allow authentication bypass.

**Independent Test**: Deploy to Lambda, trigger mock token generation path, verify RuntimeError is raised and no tokens are returned.

**Acceptance Scenarios**:

1. **Given** the application is running in AWS Lambda (AWS_LAMBDA_FUNCTION_NAME is set), **When** `_generate_tokens()` is called, **Then** a RuntimeError is raised with message indicating mock tokens are disabled in Lambda
2. **Given** the application is running in AWS Lambda, **When** authentication flow would normally generate mock tokens, **Then** the request fails before any token is returned to the client
3. **Given** the application is running in AWS Lambda, **When** RuntimeError is raised, **Then** the error is logged for security monitoring

---

### User Story 2 - Local Development Continues to Work (Priority: P1)

Developers running the application locally (outside Lambda) must continue to receive mock tokens for testing and development purposes.

**Why this priority**: Development velocity must not be impacted. Local testing is essential.

**Independent Test**: Run application locally without AWS_LAMBDA_FUNCTION_NAME, verify mock tokens are generated normally.

**Acceptance Scenarios**:

1. **Given** the application is running locally (AWS_LAMBDA_FUNCTION_NAME is not set), **When** `_generate_tokens()` is called, **Then** mock tokens are generated as before
2. **Given** the application is running in test environment without Lambda, **When** authentication flow runs, **Then** mock tokens work normally

---

### User Story 3 - Clear Error Messages for Debugging (Priority: P2)

When mock token generation is blocked in Lambda, the error message must clearly indicate why and suggest the proper solution (use real Cognito tokens).

**Why this priority**: Operators debugging production issues need clear guidance.

**Independent Test**: Trigger the error in Lambda, verify error message contains actionable information.

**Acceptance Scenarios**:

1. **Given** mock token generation is blocked in Lambda, **When** the error is logged, **Then** the message explains that production must use Cognito tokens
2. **Given** mock token generation fails, **When** operator reviews logs, **Then** they understand the root cause without additional investigation

---

### Edge Cases

- What happens when AWS_LAMBDA_FUNCTION_NAME is set to empty string? System treats as local development (empty string is falsy in Python)
- What happens when running in LocalStack Lambda emulation? LocalStack sets AWS_LAMBDA_FUNCTION_NAME, so mock tokens are blocked - this is correct behavior as it validates production paths
- How does system handle if error occurs mid-authentication? Authentication fails cleanly, no partial state is left

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST check for `AWS_LAMBDA_FUNCTION_NAME` environment variable at the start of `_generate_tokens()` function
- **FR-002**: System MUST raise `RuntimeError` with descriptive message when mock token generation is attempted in Lambda environment
- **FR-003**: System MUST allow mock token generation when `AWS_LAMBDA_FUNCTION_NAME` is not set or is empty
- **FR-004**: System MUST NOT modify the mock token format or structure (maintain backward compatibility for local development)
- **FR-005**: System MUST log the blocked attempt at ERROR level for security monitoring

### Non-Functional Requirements

- **NFR-001**: Guard check adds negligible latency (single environment variable lookup)
- **NFR-002**: No new dependencies required

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of mock token generation attempts in Lambda environment are blocked
- **SC-002**: 100% of mock token generation attempts in local environment succeed unchanged
- **SC-003**: All blocked attempts are logged with sufficient detail for security audit
- **SC-004**: Zero breaking changes to local development workflow

## Assumptions

1. `AWS_LAMBDA_FUNCTION_NAME` is the canonical way to detect Lambda environment (AWS documentation confirms this)
2. LocalStack sets this variable when emulating Lambda, so tests using LocalStack will exercise the production path
3. Production will eventually use real Cognito tokens - this guard is a safety net during transition

## Out of Scope

- Implementing real Cognito token generation (separate feature)
- Removing the mock token function entirely (Phase 3 cleanup)
- Modifying other authentication code paths
