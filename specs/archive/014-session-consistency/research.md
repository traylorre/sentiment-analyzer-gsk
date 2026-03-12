# Research: Multi-User Session Consistency

**Feature**: 014-session-consistency
**Date**: 2025-12-01
**Status**: Complete

## Research Summary

This document captures the technical research and decisions made during Phase 0 planning for the session consistency feature. All "NEEDS CLARIFICATION" items from the spec have been resolved through user clarification sessions.

---

## 1. Authentication Header Strategy

### Decision
**Hybrid approach**: Backend accepts both `X-User-ID` header and `Authorization: Bearer` token.

### Rationale
- **Backward compatibility**: Existing traffic generator and test tools use `X-User-ID`
- **Future-ready**: New frontend code can migrate to `Authorization: Bearer`
- **Gradual migration**: No breaking changes required during transition
- **Industry standard**: Bearer tokens align with OAuth 2.0/JWT conventions

### Alternatives Considered
| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| X-User-ID only | Simple, no changes needed | Non-standard, no token validation | Doesn't scale for authenticated users |
| Bearer only | Industry standard | Breaking change for existing tools | Requires coordinated migration |
| **Hybrid (chosen)** | Best of both, gradual migration | Slightly more code | Chosen for zero downtime migration |

### Implementation Pattern
```python
def extract_user_id(request: Request) -> str | None:
    """Extract user ID from either header format."""
    # Try Bearer token first (preferred)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return validate_and_extract_user_id(token)

    # Fall back to X-User-ID (legacy)
    return request.headers.get("X-User-ID")
```

### Source Files
- Current X-User-ID usage: `src/lambdas/dashboard/router_v2.py:125-154`
- Current Bearer usage: `frontend/src/lib/api/client.ts:84-87`

---

## 2. Anonymous Session Auto-Creation Timing

### Decision
**On app load**: Create anonymous session immediately when React app mounts, before any user interaction.

### Rationale
- **Zero perceived latency**: Session ready before user clicks anything
- **Consistent UX**: All API calls have valid session from start
- **Tab synchronization**: localStorage shared across tabs immediately
- **Root cause fix**: Directly addresses "No sentiment data" bug

### Alternatives Considered
| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| On first API call | Lazy, minimal overhead | Race conditions, failed first requests | User sees errors before session exists |
| On user interaction | Deferred work | Unpredictable timing, button clicks fail | Poor UX, visible delays |
| **On app load (chosen)** | Immediate, consistent | Slightly more initial requests | Best UX, directly fixes the bug |

### Implementation Pattern
```tsx
// SessionProvider wraps app at root level
function SessionProvider({ children }: Props) {
  const { user, signInAnonymous, isLoading } = useAuthStore();

  useEffect(() => {
    // Auto-create session if none exists
    if (!user && !isLoading) {
      signInAnonymous();
    }
  }, [user, isLoading, signInAnonymous]);

  return <>{children}</>;
}
```

### Source Files
- Current auth store: `frontend/src/stores/auth-store.ts:84-100` (`signInAnonymous`)
- App root (to wrap): `frontend/src/app/layout.tsx`

---

## 3. Server-Side Session Revocation

### Decision
**Yes for all sessions** (anonymous + authenticated), integrated with existing andon cord/feature flag system.

### Rationale
- **Security incidents**: Rapid response capability for breaches
- **Compliance**: Session invalidation required for GDPR/SOC2
- **Operational control**: Can disable compromised accounts immediately
- **Existing infrastructure**: Andon cord system already deployed

### Alternatives Considered
| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| Client-side only | Simpler | No server control, vulnerable | Can't respond to security incidents |
| Authenticated only | Less code | Anonymous sessions unprotectable | Leaves gap in security posture |
| **All + andon cord (chosen)** | Complete coverage | More complexity | Security is non-negotiable |

### Implementation Pattern
```python
# User model addition
class User(BaseModel):
    revoked: bool = False
    revoked_at: datetime | None = None
    revoked_reason: str | None = None

# Session validation check
def validate_session(user_id: str, table) -> bool:
    user = get_user(user_id, table)
    if user.revoked:
        raise SessionRevokedException(user.revoked_reason)
    return True

# Andon cord integration
def revoke_all_sessions(reason: str, scope: str = "all"):
    """Bulk revocation via feature flag trigger."""
    # Update feature flag to trigger revocation
    # Optionally: batch update all user records
```

### Source Files
- Existing andon cord: `src/lambdas/shared/feature_flags.py` (to research)
- User model: `src/lambdas/shared/models/user.py`

---

## 4. Email Uniqueness Enforcement

### Decision
**Database constraint** via GSI with conditional write (`attribute_not_exists(email)`).

### Rationale
- **Guaranteed atomic**: DynamoDB handles concurrency at database level
- **No race conditions**: Conditional writes prevent duplicates by design
- **Best practice**: DynamoDB GSI pattern from constitution §5
- **Performance**: GSI enables O(1) email lookup vs O(n) scan

### Alternatives Considered
| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| Application check + write | Simple code | Race condition window | Two concurrent creates can both succeed |
| Transactional write | Strong consistency | More complex, higher cost | Overkill for single attribute |
| **GSI + conditional (chosen)** | Atomic, fast lookup | Requires GSI setup | Best balance of safety and performance |

### Implementation Pattern
```python
# DynamoDB GSI definition (Terraform)
# GSI: email-index
#   Partition Key: email
#   Sort Key: entity_type
#   Projection: KEYS_ONLY

# Conditional write pattern
def create_user_with_email(user: User, table) -> bool:
    try:
        table.put_item(
            Item=user.to_dynamodb_item(),
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(email)"
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise EmailAlreadyExistsError(user.email)
        raise
```

### GSI Design
```
GSI: email-index
├── Partition Key: email (string)
├── Sort Key: entity_type (string) - allows filtering PROFILE vs other types
├── Projection: KEYS_ONLY (minimal storage, just need existence check)
└── Sparse: Only items with email attribute are indexed
```

### Source Files
- Current user model: `src/lambdas/shared/models/user.py`
- Current email lookup (scan): `src/lambdas/dashboard/auth.py:344-375`
- DynamoDB module: `infrastructure/terraform/modules/dynamodb/main.tf`

---

## 5. Atomic Magic Link Token Verification

### Decision
**Conditional update** that atomically checks `used=false` and sets `used=true`.

### Rationale
- **Race condition proof**: Single atomic operation prevents double-use
- **Audit trail**: `used_at` timestamp captures exact verification time
- **Existing pattern**: Similar to quota conditional writes

### Implementation Pattern
```python
def verify_and_consume_token(token_id: str, table) -> MagicLinkToken:
    """Atomically verify token is unused and mark it used."""
    try:
        response = table.update_item(
            Key={"PK": f"TOKEN#{token_id}", "SK": "MAGIC_LINK"},
            UpdateExpression="SET #used = :true, #used_at = :now",
            ConditionExpression="#used = :false AND #expires_at > :now",
            ExpressionAttributeNames={
                "#used": "used",
                "#used_at": "used_at",
                "#expires_at": "expires_at"
            },
            ExpressionAttributeValues={
                ":true": True,
                ":false": False,
                ":now": datetime.utcnow().isoformat()
            },
            ReturnValues="ALL_NEW"
        )
        return MagicLinkToken.from_dynamodb_item(response["Attributes"])
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise TokenAlreadyUsedOrExpiredError(token_id)
        raise
```

### Source Files
- Current verification: `src/lambdas/dashboard/auth.py:695-808`
- Token model: `src/lambdas/shared/models/magic_link_token.py`

---

## 6. Account Merge Strategy

### Decision
**Tombstone + idempotency keys**: Mark source items with `merged_to` field before copying.

### Rationale
- **Self-healing**: Partial failures can be retried without duplicates
- **Audit trail**: Clear record of what was merged where
- **No item limit**: Works for any number of items (vs transactions)
- **Existing pattern**: Similar to DynamoDB best practices

### Implementation Pattern
```python
def merge_anonymous_to_authenticated(
    anonymous_user_id: str,
    authenticated_user_id: str,
    table
) -> MergeResult:
    """Idempotent merge with tombstone markers."""
    items_to_merge = query_user_items(anonymous_user_id, table)

    for item in items_to_merge:
        # Skip already-merged items (idempotency)
        if item.get("merged_to"):
            continue

        # Step 1: Mark source with tombstone FIRST
        table.update_item(
            Key={"PK": item["PK"], "SK": item["SK"]},
            UpdateExpression="SET merged_to = :target, merged_at = :now",
            ExpressionAttributeValues={
                ":target": authenticated_user_id,
                ":now": datetime.utcnow().isoformat()
            }
        )

        # Step 2: Copy to target (can retry safely)
        new_item = copy_item_to_user(item, authenticated_user_id)
        table.put_item(Item=new_item)

    return MergeResult(
        source_user_id=anonymous_user_id,
        target_user_id=authenticated_user_id,
        items_merged=len(items_to_merge)
    )
```

### Source Files
- Current merge: `src/lambdas/shared/auth/merge.py:41-130`

---

## 7. Race Condition Testing Strategy

### Decision
**Async concurrency with pytest-asyncio** using `asyncio.gather()` to fire concurrent requests.

### Rationale
- **True I/O parallelism**: asyncio handles concurrent HTTP requests properly
- **Existing patterns**: Matches repo's E2E test structure
- **Deterministic**: Can control timing and verify exact outcomes

### Implementation Pattern
```python
import pytest
import asyncio
from httpx import AsyncClient

@pytest.mark.asyncio
@pytest.mark.session_consistency
@pytest.mark.session_us2
async def test_concurrent_magic_link_verification():
    """Exactly one verification succeeds when 10 concurrent requests race."""
    token = await create_magic_link_token("test@example.com")

    async with AsyncClient(base_url=API_URL) as client:
        # Fire 10 concurrent verification requests
        tasks = [
            client.post(f"/api/v2/auth/magic-link/verify", json={"token": token})
            for _ in range(10)
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify exactly one success
    successes = [r for r in responses if r.status_code == 200]
    failures = [r for r in responses if r.status_code == 409]  # Conflict

    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
    assert len(failures) == 9, f"Expected 9 failures, got {len(failures)}"
```

### Test Markers (to add to pytest.ini)
```ini
[pytest]
markers =
    session_consistency: Feature 014 - Session consistency tests
    session_us1: User Story 1 - Consistent session across tabs
    session_us2: User Story 2 - Concurrent magic link verification
    session_us3: User Story 3 - Email uniqueness guarantee
    session_us4: User Story 4 - Session refresh
    session_us5: User Story 5 - Atomic account merge
    session_us6: User Story 6 - Fast email lookup
```

### Source Files
- Current pytest config: `pytest.ini`
- E2E test patterns: `tests/e2e/test_auth_anonymous.py`

---

## 8. Test Coverage Strategy

### Decision
**Full pyramid** (unit + integration + contract + E2E) for each FR, with 80% coverage threshold.

### Test File Mapping
| Functional Requirement | Test File | Test Type |
|----------------------|-----------|-----------|
| FR-001, FR-002, FR-003 | `tests/unit/lambdas/shared/auth/test_session_consistency.py` | Unit |
| FR-004, FR-005, FR-006 | `tests/unit/lambdas/shared/auth/test_atomic_token_verification.py` | Unit |
| FR-007, FR-008, FR-009 | `tests/unit/lambdas/shared/auth/test_email_uniqueness.py` | Unit |
| FR-010, FR-011, FR-012 | `tests/unit/lambdas/shared/auth/test_session_lifecycle.py` | Unit |
| FR-013, FR-014, FR-015 | `tests/unit/lambdas/shared/auth/test_merge_idempotency.py` | Unit |
| FR-016, FR-017 | `tests/unit/lambdas/shared/auth/test_session_revocation.py` | Unit |
| Race conditions (all) | `tests/integration/test_session_race_conditions.py` | Integration |
| API schemas | `tests/contract/test_session_api_v2.py` | Contract |
| Real AWS validation | `tests/e2e/test_session_consistency_preprod.py` | E2E |

### Frontend Tests (vitest)
| Component | Test File |
|-----------|-----------|
| Auth store | `frontend/src/stores/__tests__/auth-store.test.ts` |
| Session init hook | `frontend/src/hooks/__tests__/use-session-init.test.ts` |
| Session provider | `frontend/src/components/providers/__tests__/session-provider.test.tsx` |

---

## Dependencies and Integration Points

### Existing Code to Leverage
1. **Quota conditional writes**: `src/lambdas/dashboard/quota.py:85-166` - Pattern for atomic counters
2. **Zustand persistence**: `frontend/src/stores/auth-store.ts:307-318` - LocalStorage middleware
3. **E2E API client**: `tests/e2e/helpers/api_client.py` - Async HTTP patterns
4. **User model**: `src/lambdas/shared/models/user.py` - DynamoDB serialization

### New Infrastructure Required
1. **Email GSI**: Add to DynamoDB table via Terraform
2. **pytest-asyncio**: Already installed (verify version)
3. **Feature flag integration**: Connect to existing andon cord system

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GSI backfill delay | Medium | Low | Deploy GSI first, wait for ACTIVE status |
| Race condition edge cases | Medium | High | Comprehensive concurrent tests with 100 requests |
| Frontend hydration issues | Low | Medium | Test SSR + client hydration separately |
| Breaking existing sessions | Medium | High | Migration script to add `revoked=false` to existing users |

---

## Clarification Session Log

All clarifications resolved via user input:

1. **Auth header strategy** → Hybrid (Q1, 2025-12-01)
2. **Anonymous session timing** → On app load (Q2, 2025-12-01)
3. **Server-side revocation** → Yes + andon cord (Q3, 2025-12-01)
4. **Email uniqueness** → Database constraint (Q4, 2025-12-01)
5. **Merge failure recovery** → Tombstone + idempotency (Q5, 2025-12-01)
6. **Race condition testing** → pytest-asyncio (Q6, 2025-12-01)
7. **Test coverage scope** → Full pyramid (Q7, 2025-12-01)
8. **Test markers** → Feature + story markers (Q8, 2025-12-01)
