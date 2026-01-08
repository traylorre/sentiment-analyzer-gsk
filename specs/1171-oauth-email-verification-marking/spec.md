# Feature 1171: OAuth Email Verification Marking

## Problem Statement

When users authenticate via OAuth (Google/GitHub), the provider JWT contains an `email_verified` claim indicating whether the provider has verified the user's email. Currently, this claim is:

1. **Extracted** from the JWT in `decode_id_token()`
2. **Passed** to `_link_provider()` which stores it as `ProviderMetadata.verified_at`
3. **NOT copied** to the user-level `verification` field

This creates a gap where OAuth-authenticated users with provider-verified emails remain at `verification="none"`, blocking:
- Role upgrades requiring verified email (per Feature 1163 role-verification state machine)
- RBAC checks that depend on verification status
- Frontend UI that relies on verification state

## Root Cause

Feature 1169 (`_link_provider()`) stores verification per-provider as a timestamp, but doesn't propagate to the canonical user-level `verification` field. The two-level model (provider-level vs user-level verification) was intentionally designed but the propagation step was missing.

## Solution

Add `_mark_email_verified()` helper function following the `_advance_role()` pattern (Feature 1170):

1. **Create helper function** that updates `verification` field based on OAuth JWT claim
2. **Call from both OAuth paths** (existing user + new user) in `handle_oauth_callback()`
3. **Call BEFORE role advancement** to respect state machine invariant
4. **Follow silent failure pattern** - log warning but don't break OAuth flow

## Technical Specification

### New Function: `_mark_email_verified()`

**Signature:**
```python
def _mark_email_verified(
    table: Any,
    user: User,
    provider: str,
    email: str,
    email_verified: bool,
) -> None:
```

**Logic:**
1. If `email_verified=False`, skip with debug log
2. If `user.verification` already `"verified"`, skip with debug log
3. Update DynamoDB: set `verification="verified"`, `primary_email=email`
4. Add audit field `verification_marked_at` and `verification_marked_by`
5. Wrap in try/except, log warning on failure, don't raise

### Integration Points

**Existing User Path (line ~1604):**
```python
_link_provider(...)
_mark_email_verified(
    table=table,
    user=user,
    provider=request.provider,
    email=email,
    email_verified=claims.get("email_verified", False),
)
_advance_role(...)
```

**New User Path (line ~1629):**
```python
_link_provider(...)
_mark_email_verified(
    table=table,
    user=user,
    provider=request.provider,
    email=email,
    email_verified=claims.get("email_verified", False),
)
_advance_role(...)
```

### State Machine Compliance

Per Feature 1163 role-verification invariant:
- `anonymous:none` → Mark verified → `anonymous:verified` → `_advance_role()` → `free:verified`
- This order ensures the state machine validator never sees invalid intermediate states

### DynamoDB Update Expression

```python
UpdateExpression="SET verification = :verified, primary_email = :email, verification_marked_at = :marked_at, verification_marked_by = :marked_by"
ExpressionAttributeValues={
    ":verified": "verified",
    ":email": email,
    ":marked_at": now.isoformat(),
    ":marked_by": f"oauth:{provider}",
}
```

## Acceptance Criteria

1. OAuth login with `email_verified=true` sets `user.verification="verified"`
2. OAuth login with `email_verified=false` leaves `user.verification` unchanged
3. Already-verified users are not re-marked (idempotent)
4. `primary_email` is set to the OAuth email when marking verified
5. Audit fields (`verification_marked_at`, `verification_marked_by`) populated
6. OAuth flow succeeds even if marking fails (silent failure pattern)
7. Unit tests cover all paths with 100% coverage

## Out of Scope

- Magic link verification flow (separate feature)
- Manual email verification flow
- Removing/changing verification status
- Provider-level verification display in UI (Feature 1172+)

## Dependencies

- **Requires:** Feature 1169 (OAuth federation fields) - MERGED
- **Requires:** Feature 1170 (role advancement) - MERGED
- **Blocks:** Features 1172-1175 (frontend federation)

## Testing Strategy

### Unit Tests

1. `test_mark_verified_when_provider_verified` - Happy path
2. `test_skip_when_provider_not_verified` - email_verified=False
3. `test_skip_when_already_verified` - user already verified
4. `test_sets_primary_email` - Confirm email field updated
5. `test_sets_audit_fields` - Confirm timestamps/attribution
6. `test_silent_failure_on_dynamodb_error` - Don't break OAuth flow
7. `test_integration_with_role_advancement` - Full OAuth callback flow

### Test Pattern

Follow `tests/unit/dashboard/test_role_advancement.py` structure.

## References

- Feature 1163: Role-Verification State Machine
- Feature 1169: OAuth Federation Fields
- Feature 1170: Role Advancement Pattern
- `src/lambdas/dashboard/auth.py:1526-1652` (OAuth callback)
- `src/lambdas/shared/models/user.py:92-100` (verification field)
