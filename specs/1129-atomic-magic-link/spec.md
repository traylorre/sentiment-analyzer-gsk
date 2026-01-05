# Feature Specification: Atomic Magic Link Token Consumption

**Feature Branch**: `1129-atomic-magic-link`
**Created**: 2026-01-05
**Status**: Implemented
**Input**: User description: "Phase 0 C3: Implement atomic magic link token consumption using DynamoDB conditional update. Prevents race condition token reuse."
**Context**: Part of Phase 0 Security Blocking for HTTPOnly cookie migration. Related spec: specs/1126-auth-httponly-migration/spec-v2.md

## Problem Statement

The current `verify_magic_link()` function (auth.py lines 1364-1476) uses a non-atomic get-then-update pattern that is vulnerable to race conditions:

1. Request A and Request B both fetch the same token simultaneously
2. Both see `used=false` and pass validation
3. Both call `update_item()` without a condition
4. **Both succeed** - token is consumed twice, enabling replay attacks

A safe atomic function `verify_and_consume_token()` already exists (lines 1236-1360) but the router endpoint (router_v2.py line 348) still calls the vulnerable non-atomic function.

**Security Risk**: Magic link tokens can be reused in a race condition window, enabling:
1. Unauthorized session creation
2. Token replay attacks
3. Session hijacking if attacker intercepts link

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Atomic Token Consumption Prevents Replay (Priority: P1)

When a user clicks a magic link, the token must be consumed atomically so that concurrent requests cannot both succeed. Only the first request wins; subsequent requests fail immediately.

**Why this priority**: This is a critical security control. Race conditions enable authentication bypass.

**Independent Test**: Send two concurrent requests with the same token; verify exactly one succeeds and one fails with 409 Conflict.

**Acceptance Scenarios**:

1. **Given** a valid magic link token, **When** two requests arrive simultaneously, **Then** exactly one succeeds with session tokens and exactly one fails with 409 Conflict
2. **Given** a valid magic link token, **When** the first request consumes it, **Then** the token is marked used atomically before any response is sent
3. **Given** a consumed token, **When** any subsequent request arrives, **Then** the system rejects it with clear "already used" error

---

### User Story 2 - Expired Tokens Are Rejected (Priority: P1)

Tokens that have passed their expiration time must be rejected even if not yet consumed.

**Why this priority**: Expired tokens are a security risk even without race conditions.

**Independent Test**: Create a token with past expiration, attempt to use it, verify 410 Gone response.

**Acceptance Scenarios**:

1. **Given** a token with `expires_at` in the past, **When** a request attempts to use it, **Then** the system rejects with 410 Gone
2. **Given** a valid token, **When** it expires between fetch and update, **Then** the atomic condition prevents consumption

---

### User Story 3 - Audit Trail for Token Consumption (Priority: P2)

When a token is consumed, the system must record when and from where for security auditing.

**Why this priority**: Audit trails enable forensic investigation of potential attacks.

**Independent Test**: Consume a token, verify `used_at` timestamp and `used_by_ip` are recorded.

**Acceptance Scenarios**:

1. **Given** a valid magic link token, **When** consumed successfully, **Then** `used_at` records the exact timestamp
2. **Given** a valid magic link token, **When** consumed successfully, **Then** `used_by_ip` records the client IP address
3. **Given** audit records exist, **When** security team investigates, **Then** they can trace which IP used which token and when

---

### Edge Cases

- What happens when database write fails after condition check passes? Transaction fails atomically, token remains unused
- What happens when token is used during database maintenance? Request fails, user can request new magic link
- How does system handle clock skew for expiration? Server time is authoritative; token expiration uses server-side check

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST use conditional database update with `used = false AND expires_at > now` condition
- **FR-002**: System MUST return 200 OK with session tokens only when atomic update succeeds
- **FR-003**: System MUST return 409 Conflict when token is already used (condition check fails)
- **FR-004**: System MUST return 410 Gone when token is expired
- **FR-005**: System MUST record `used_at` timestamp when token is consumed
- **FR-006**: System MUST record `used_by_ip` address when token is consumed
- **FR-007**: System MUST update router to use atomic verification function instead of non-atomic one

### Non-Functional Requirements

- **NFR-001**: Atomic operation completes in single database roundtrip (no separate get then update)
- **NFR-002**: No additional latency compared to non-atomic pattern (same number of DB calls)

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of concurrent token consumption attempts result in exactly one success
- **SC-002**: 100% of expired tokens are rejected regardless of race timing
- **SC-003**: All consumed tokens have complete audit records (used_at, used_by_ip)
- **SC-004**: Zero authentication bypasses possible through token replay

## Key Entities

- **MagicLinkToken**: Token entity with fields: `token_id`, `user_id`, `email`, `expires_at`, `used`, `used_at`, `used_by_ip`
- **Session**: Created upon successful token consumption

## Assumptions

1. The atomic `verify_and_consume_token()` function already exists and is tested
2. The router endpoint at router_v2.py:348 needs to be updated to call the atomic function
3. The token model already has `used_at` and `used_by_ip` fields
4. Error classes `TokenAlreadyUsedError` and `TokenExpiredError` already exist

## Out of Scope

- Creating the atomic function from scratch (already exists)
- Modifying the token model (already has required fields)
- Creating new error types (already exist)
- Rate limiting magic link requests (separate feature)
