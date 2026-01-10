# Research: OAuth Auto-Link for Email-Verified Users

## Decision 1: Domain-Based Auto-Link Detection

**Decision**: Only auto-link when Google OAuth + @gmail.com email. All other cases require manual confirmation.

**Rationale**:
- Google is authoritative for @gmail.com domain - if Google says the email is verified, it's trustworthy
- GitHub is opaque - email is not the primary identifier, `sub` claim is
- Cross-domain scenarios (e.g., @hotmail.com + Google OAuth) have ambiguity about identity ownership
- Industry standard: Auth0 uses similar domain-matching for automatic account linking

**Alternatives Considered**:
- Auto-link all verified emails: Rejected due to security risk (email spoofing)
- Always prompt: Rejected as it degrades UX for the most common case (Gmail users)

## Decision 2: Duplicate Provider Sub Protection

**Decision**: Use `get_user_by_provider_sub()` (Feature 1180) to check if OAuth account is already linked to a different user before proceeding.

**Rationale**:
- Prevents account takeover via OAuth email spoofing
- OAuth `sub` claim is immutable and unique per provider
- GSI on `provider_sub` enables O(1) lookup

**Alternatives Considered**:
- Email-based lookup: Rejected because emails can change or be spoofed
- Skip check: Rejected due to security risk

## Decision 3: Existing `_link_provider()` Reuse

**Decision**: Leverage existing `_link_provider()` function which already:
- Updates `linked_providers` array
- Sets `provider_sub` for GSI indexing
- Updates `last_provider_used`

**Rationale**:
- Function already exists at auth.py:1831-1843
- Handles the DynamoDB update expression correctly
- Sets provider_sub in format `{provider}:{sub}`

**Alternatives Considered**:
- New function: Rejected - would duplicate existing code

## Decision 4: Audit Event Type

**Decision**: Log `AuthEventType.AUTH_METHOD_LINKED` with `link_type` field indicating "auto" or "manual".

**Rationale**:
- Existing audit event type covers linking operations
- Adding `link_type` field distinguishes auto vs manual linking
- Enables compliance auditing and debugging

**Alternatives Considered**:
- Separate event types: Rejected - one event type with metadata is cleaner

## Decision 5: Frontend Linking Prompt

**Decision**: Create `LinkAccountPrompt.tsx` component with two buttons: "Link Accounts" and "Use [Provider] Only".

**Rationale**:
- Clear user choice between linking and separate identity
- Follows existing modal pattern in frontend
- Email addresses shown masked for privacy (e.g., "c**@gmail.com")

**Alternatives Considered**:
- Inline prompt: Rejected - modal better captures user attention for security decision
