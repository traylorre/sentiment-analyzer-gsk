# Feature Specification: OAuth Callback Federation Response

**Feature Branch**: `1176-oauth-callback-federation-response`
**Created**: 2025-01-09
**Status**: Draft
**Input**: Add federation fields to OAuthCallbackResponse so frontend receives updated federation state after OAuth authentication.

## User Scenarios & Testing

### User Story 1 - Receive Federation State After OAuth (Priority: P1)

A user authenticates via OAuth (Google/GitHub). After successful authentication, the frontend receives the updated federation state (role, verification status, linked providers) directly in the OAuth callback response, enabling immediate RBAC-aware UI decisions without a separate API call.

**Why this priority**: This is the core gap blocking federation functionality. Backend updates DynamoDB but response doesn't include the data.

**Independent Test**: After OAuth callback, response body contains `role`, `verification`, `linked_providers`, `last_provider_used` fields with correct values.

**Acceptance Scenarios**:

1. **Given** anonymous user with no linked providers, **When** user authenticates via Google OAuth with verified email, **Then** response contains `role="free"`, `verification="verified"`, `linked_providers=["google"]`, `last_provider_used="google"`

2. **Given** existing free user with Google linked, **When** user authenticates via GitHub OAuth, **Then** response contains `role="free"` (unchanged), `linked_providers=["google", "github"]`, `last_provider_used="github"`

3. **Given** user with unverified email from OAuth provider, **When** user completes OAuth callback, **Then** response contains `verification="none"` (not auto-verified)

---

### User Story 2 - Contract Backward Compatibility (Priority: P2)

Existing frontend code continues working. New fields are optional/additive - no breaking changes to existing response schema.

**Why this priority**: Must not break existing OAuth flows during migration.

**Independent Test**: Existing contract tests pass without modification. New fields are all optional with defaults.

**Acceptance Scenarios**:

1. **Given** existing frontend consuming OAuth response, **When** response includes new federation fields, **Then** frontend ignores unknown fields gracefully (standard JSON behavior)

2. **Given** OAuthCallbackResponse model, **When** serialized to JSON, **Then** all new fields have defaults (role="anonymous", verification="none", linked_providers=[], last_provider_used=None)

---

### Edge Cases

- What happens when `_advance_role()` fails to update DynamoDB but `_link_provider()` succeeds? Response should still include whatever state was successfully written.
- What happens during conflict flow? Conflict responses don't go through full federation logic; federation fields should be omitted or use defaults.
- What happens for magic link auth? This feature is OAuth-specific; magic link uses different response model.

## Requirements

### Functional Requirements

- **FR-001**: `OAuthCallbackResponse` MUST include `role: str` field with default "anonymous"
- **FR-002**: `OAuthCallbackResponse` MUST include `verification: str` field with default "none"
- **FR-003**: `OAuthCallbackResponse` MUST include `linked_providers: list[str]` field with default empty list
- **FR-004**: `OAuthCallbackResponse` MUST include `last_provider_used: str | None` field with default None
- **FR-005**: `handle_oauth_callback()` MUST populate federation fields from the updated User object after calling `_link_provider()`, `_mark_email_verified()`, `_advance_role()`
- **FR-006**: Error and conflict responses MAY omit federation fields (use defaults)
- **FR-007**: New fields MUST be optional to maintain backward compatibility

### Key Entities

- **OAuthCallbackResponse**: Pydantic model at `auth.py:999-1017` - add federation fields
- **User**: Source of federation data after DynamoDB updates
- **Federation fields**: role, verification, linked_providers, last_provider_used

## Success Criteria

### Measurable Outcomes

- **SC-001**: All existing OAuth unit tests pass without modification
- **SC-002**: All existing OAuth contract tests pass without modification
- **SC-003**: New unit tests verify federation fields are populated correctly in successful OAuth response
- **SC-004**: Frontend can read `role` from OAuth response to make RBAC decisions

## Technical Context

### Current State (Lines from auth.py)

**OAuthCallbackResponse (lines 999-1017):**
```python
class OAuthCallbackResponse(BaseModel):
    status: str
    email_masked: str | None = None
    auth_type: str | None = None
    tokens: dict | None = None
    refresh_token_for_cookie: str | None = None
    merged_anonymous_data: bool = False
    is_new_user: bool = False
    conflict: bool = False
    existing_provider: str | None = None
    message: str | None = None
    error: str | None = None
    # MISSING: role, verification, linked_providers, last_provider_used
```

**handle_oauth_callback return (lines 1654-1668):**
```python
return OAuthCallbackResponse(
    status="authenticated",
    email_masked=_mask_email(email),
    auth_type=f"oauth:{provider_name}",
    tokens={"access_token": access_token},
    refresh_token_for_cookie=refresh_token,
    merged_anonymous_data=merged_anonymous,
    is_new_user=is_new_user,
    # MISSING: federation fields from updated user
)
```

### Required Changes

1. Add 4 fields to `OAuthCallbackResponse` (lines 999-1017)
2. Populate fields in successful return at lines 1654-1668 from User object
3. Add unit tests for federation field population
