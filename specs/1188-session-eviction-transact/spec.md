# Feature Specification: Session Eviction Atomic Transaction

**Feature Branch**: `1188-session-eviction-transact`
**Created**: 2026-01-10
**Status**: Draft
**Input**: User description: "A11: Session eviction must use TransactWriteItems for atomic deletion of user sessions. Prevent partial deletion race conditions."
**Source Requirement**: spec-v2.md A11 (CRITICAL)

## Problem Statement

The current session eviction implementation (spec-v2.md lines 3991-4025) uses non-atomic operations when enforcing session limits. This creates a race condition where:

1. User has max sessions (e.g., 5)
2. Two concurrent login requests both check session count = 5
3. Both decide to evict oldest session
4. Both delete the same oldest session
5. Both create new sessions
6. User ends up with 6 sessions (limit bypassed)

This allows attackers to bypass session limits through concurrent requests, potentially enabling:
- Unlimited parallel sessions from compromised accounts
- Session limit abuse for denial-of-service
- Token proliferation making revocation ineffective

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Session Limit Enforcement (Priority: P1)

A user attempts to log in when they already have the maximum allowed sessions active. The system must evict the oldest session and create a new one atomically, ensuring the session limit is never exceeded.

**Why this priority**: Core security requirement. Bypassing session limits defeats the purpose of having limits at all. Must be bulletproof.

**Independent Test**: Can be tested by simulating concurrent login requests with a user at session limit and verifying final session count never exceeds limit.

**Acceptance Scenarios**:

1. **Given** user has 5 active sessions (at limit), **When** user logs in from new device, **Then** oldest session is evicted AND new session created in single atomic operation AND total remains 5
2. **Given** user has 5 sessions, **When** 10 concurrent login requests arrive, **Then** final session count is exactly 5 AND no race condition allows extra sessions
3. **Given** user has 3 sessions (under limit), **When** user logs in, **Then** no eviction occurs AND new session created normally

---

### User Story 2 - Evicted Token Blocklist (Priority: P1)

When a session is evicted due to limit enforcement, its refresh token must be immediately blocklisted to prevent the evicted session from refreshing and creating a new valid session.

**Why this priority**: Without blocklisting, evicted sessions can "resurrect" by refreshing, defeating the eviction.

**Independent Test**: Can be tested by evicting a session and immediately attempting to refresh with its token.

**Acceptance Scenarios**:

1. **Given** session is evicted due to limit enforcement, **When** evicted session attempts token refresh, **Then** refresh is rejected with appropriate error
2. **Given** session is evicted, **When** blocklist entry is written, **Then** entry includes TTL matching refresh token expiration
3. **Given** refresh endpoint receives token, **When** processing request, **Then** blocklist is checked BEFORE any token issuance

---

### User Story 3 - Race Condition Retry (Priority: P2)

When the atomic transaction fails due to concurrent modification (another request already evicted the target session), the system should return a retriable error to the client.

**Why this priority**: Graceful handling of expected race conditions. Allows clients to retry without manual intervention.

**Independent Test**: Can be tested by forcing transaction conflict and verifying retriable error response.

**Acceptance Scenarios**:

1. **Given** atomic transaction fails due to condition check failure, **When** TransactionCanceledException occurs, **Then** system returns SessionLimitRaceError with retry guidance
2. **Given** client receives SessionLimitRaceError, **When** client retries login, **Then** second attempt succeeds with fresh session
3. **Given** transaction fails, **When** error is returned, **Then** no partial writes exist (no orphan blocklist entries, no orphan sessions)

---

### Edge Cases

- What happens when the oldest session to evict is deleted between condition check and transaction execution? Transaction fails with ConditionCheckFailure, client receives SessionLimitRaceError and retries
- What happens when blocklist write succeeds but session delete fails? Not possible - TransactWriteItems is atomic, all succeed or all fail
- What happens when DynamoDB throttles the transaction? Standard DynamoDB retry with exponential backoff before returning error
- What happens when the refresh token is already on the blocklist? Reject refresh before transaction, no eviction logic needed

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST use DynamoDB TransactWriteItems for all session eviction operations
- **FR-002**: Transaction MUST include ConditionCheck verifying oldest session still exists before deletion
- **FR-003**: Transaction MUST include Delete operation for the oldest session
- **FR-004**: Transaction MUST include Put operation adding evicted token hash to blocklist with format `BLOCK#refresh#{hash}`
- **FR-005**: Transaction MUST include Put operation for new session with `attribute_not_exists(PK)` condition
- **FR-006**: Blocklist entries MUST have TTL matching refresh token expiration time
- **FR-007**: Refresh endpoint MUST check blocklist BEFORE issuing any new tokens
- **FR-008**: System MUST return SessionLimitRaceError when TransactionCanceledException occurs due to condition check failure
- **FR-009**: All four transaction operations MUST succeed or fail together (atomicity guarantee)

### Key Entities

- **Session**: User session record with user_id, session_id, created_at, refresh_token_hash
- **Blocklist Entry**: Revoked token record with key `BLOCK#refresh#{hash}`, TTL for automatic cleanup
- **User**: The account subject to session limits (max 5 concurrent sessions)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Under 100 concurrent login attempts from same user, final session count equals configured limit (never exceeds)
- **SC-002**: Evicted session refresh tokens are rejected within 100ms of eviction
- **SC-003**: Transaction failure rate due to race conditions is below 5% under normal load
- **SC-004**: 100% of failed transactions result in zero partial state (no orphan records)
- **SC-005**: Blocklist check adds less than 10ms latency to refresh token flow

## Assumptions

- DynamoDB table already has required indexes for session queries by user_id
- Blocklist entries use the same DynamoDB table with composite key pattern
- Refresh token hash is deterministically computable from the token
- Session limit is configurable but defaults to 5 concurrent sessions
- Client applications can handle retry logic for SessionLimitRaceError
