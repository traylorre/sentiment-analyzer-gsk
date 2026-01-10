# Research: Email-to-OAuth Link (Flow 4)

**Feature**: 1182-email-to-oauth-link
**Date**: 2026-01-09

## Research Questions

### 1. Existing Magic Link Pattern

**Decision**: Reuse existing magic link infrastructure with user_id context

**Rationale**: The codebase already has `generate_magic_link_token()` and `verify_magic_link()` functions in auth.py. These support:
- Token generation with email claim
- Atomic consumption via DynamoDB conditional write
- Expiry handling with TTL
- Token reuse prevention

For Flow 4, we extend by adding `user_id` to token claims so `complete_email_link()` can verify the token belongs to the initiating user.

**Alternatives Considered**:
- Separate token table for email linking: Rejected - unnecessary complexity
- Reuse same token format without user_id: Rejected - security risk (token could be used by different user)

### 2. pending_email Field Storage

**Decision**: Store pending_email directly on User record

**Rationale**: The User model already has `pending_email: str | None` field (added in Feature 1162). Storing on User record means:
- Single source of truth for pending state
- Survives session changes (user can log out and back in)
- Only one pending email per user (implicit constraint)

**Alternatives Considered**:
- Separate pending_links table: Rejected - overengineering for single-field state
- Store in session: Rejected - state lost on session expiry

### 3. Email Uniqueness Enforcement

**Decision**: Defer to database constraint level

**Rationale**: Flow 4 spec does not define behavior when linking an email already used by another user. Current implementation:
- `by_email` GSI exists for O(1) email lookups
- Email uniqueness enforced by existing account creation flows
- `link_email_to_oauth_user()` should not check uniqueness (deferred to complete step)
- `complete_email_link()` will fail if email already exists (GSI lookup)

**Alternatives Considered**:
- Pre-check email uniqueness in link initiation: Rejected - exposes email enumeration vector
- Allow duplicate emails: Rejected - violates federation model (single canonical email per user)

### 4. Audit Event Type

**Decision**: Use AUTH_METHOD_LINKED event type with link_type="manual"

**Rationale**: Spec defines `log_auth_event(AuthEventType.AUTH_METHOD_LINKED, ...)` pattern. The `link_type="manual"` distinguishes from auto-linking in Flow 3.

**Alternatives Considered**:
- New event type AUTH_EMAIL_LINKED: Rejected - AUTH_METHOD_LINKED is generic enough
- No audit logging: Rejected - required for security compliance

### 5. Error Response Codes

**Decision**: Use existing AUTH_010 for invalid/expired tokens

**Rationale**: Spec defines AUTH_010 as generic "magic link invalid" error. This prevents enumeration attacks by not distinguishing between:
- Token expired
- Token already used
- Token not found
- Token for wrong user

**Alternatives Considered**:
- Specific error codes per failure type: Rejected - information leakage risk
- HTTP 404 for not found: Rejected - timing attack vector

## Best Practices Applied

### DynamoDB Atomic Operations
- Use `ConditionExpression` for atomic state transitions
- `update_item` with condition `attribute_not_exists(linked_providers) OR NOT contains(linked_providers, :email)`
- Prevents race conditions in concurrent linking attempts

### Magic Link Security
- Include user_id in token claims for authorization
- Constant-time token comparison
- Single-use enforcement via atomic consumption
- TTL-based expiry (15-30 minutes)

### Test Patterns
- Use `freezegun` for time-dependent tests (token expiry)
- Use `moto` for DynamoDB mocking in unit tests
- Test all failure paths (already linked, expired, reused, wrong user)
