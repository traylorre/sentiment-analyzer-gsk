# Implementation Plan: Session Eviction Atomic Transaction

**Branch**: `1188-session-eviction-transact` | **Date**: 2026-01-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/1188-session-eviction-transact/spec.md`
**Source Requirement**: spec-v2.md A11 (CRITICAL)

## Summary

Implement atomic session eviction using DynamoDB TransactWriteItems to prevent race conditions when enforcing session limits. Current implementation uses non-atomic operations that allow concurrent requests to bypass session limits. The solution uses a 4-operation transaction: ConditionCheck (verify target exists), Delete (remove oldest session), Put (blocklist entry), Put (new session).

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: boto3==1.42.17, FastAPI==0.127.0, pydantic==2.12.5, aws-lambda-powertools==3.23.0
**Storage**: DynamoDB (single table: `${environment}-sentiment-users`)
**Testing**: pytest with moto mocks for DynamoDB
**Target Platform**: AWS Lambda with Function URL
**Project Type**: Serverless web backend
**Performance Goals**: <100ms transaction latency, <5% retry rate under normal load
**Constraints**: DynamoDB transaction limit of 100 items, single table design
**Scale/Scope**: 5 concurrent sessions per user maximum

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| No over-engineering | PASS | Using DynamoDB native TransactWriteItems - no custom abstractions |
| Keep solutions simple | PASS | 4-operation transaction is minimum viable for atomicity |
| No new abstractions for one-time ops | PASS | Extends existing auth.py patterns |
| No feature flags for internal changes | PASS | Direct implementation, no toggles |

## Project Structure

### Documentation (this feature)

```text
specs/1188-session-eviction-transact/
├── plan.md              # This file
├── research.md          # DynamoDB TransactWriteItems patterns
├── spec.md              # Feature specification
├── tasks.md             # Implementation tasks
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
src/lambdas/
├── dashboard/
│   └── auth.py                    # MODIFY: Add atomic session eviction
└── shared/
    ├── errors/
    │   └── session_errors.py      # MODIFY: Add SessionLimitRaceError
    └── models/
        └── user.py                # READ ONLY: Session model reference

tests/
├── unit/
│   └── dashboard/
│       └── test_session_eviction.py  # NEW: Unit tests for eviction
└── integration/
    └── test_session_race.py          # NEW: Concurrency tests
```

**Structure Decision**: Extends existing `src/lambdas/dashboard/auth.py` where session management is centralized. No new files needed except tests and error class addition.

## Implementation Approach

### Phase 1: Core Transaction

1. **Add SessionLimitRaceError** to `session_errors.py`
   - Inherits from base exception
   - Includes retry guidance in message

2. **Create `evict_oldest_session_atomic()`** in `auth.py`
   - Query user sessions by created_at (GSI or scan with filter)
   - Build TransactWriteItems with 4 operations:
     1. ConditionCheck: `attribute_exists(PK)` on oldest session
     2. Delete: Remove oldest session item
     3. Put: Blocklist entry `BLOCK#refresh#{hash}` with TTL
     4. Put: New session with `attribute_not_exists(PK)` condition
   - Handle `TransactionCanceledException` → `SessionLimitRaceError`

3. **Add blocklist check** to `refresh_session()`
   - Check `BLOCK#refresh#{hash}` before issuing tokens
   - Return 401 if blocklisted

### Phase 2: Integration

4. **Modify `create_anonymous_session()`** to call eviction logic when at limit
5. **Modify login flows** (OAuth callback, magic link verify) to enforce limits

### Phase 3: Testing

6. **Unit tests** for transaction success/failure paths
7. **Integration tests** with moto for concurrent request simulation

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| TransactWriteItems over conditional writes | Atomic all-or-nothing required; conditional writes are sequential |
| Blocklist in same table | Single table design; composite key `BLOCK#refresh#{hash}` |
| TTL on blocklist entries | Automatic cleanup matching token expiry |
| SessionLimitRaceError (retriable) | Client can retry vs permanent failure |
| No soft delete | Session deletion is acceptable; blocklist provides audit |

## DynamoDB Key Patterns

```text
# Existing patterns
USER#{user_id}#PROFILE      → User record with session_expires_at
TOKEN#{token_id}#MAGIC_LINK → Magic link token

# New patterns for this feature
BLOCK#refresh#{hash}#BLOCK  → Blocklist entry (PK, SK format TBD based on query needs)
```

## Complexity Tracking

> No constitution violations requiring justification.

| Item | Complexity | Justification |
|------|------------|---------------|
| TransactWriteItems | Low | AWS native, well-documented |
| Blocklist pattern | Low | Existing table, simple key |
| Error handling | Low | Single new exception type |
