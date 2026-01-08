# Implementation Plan: OAuth Populate Federation Fields

**Branch**: `1169-oauth-populate-federation-fields` | **Date**: 2026-01-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1169-oauth-populate-federation-fields/spec.md`

## Summary

Implement `_link_provider()` helper function in `auth.py` to populate User federation fields (`linked_providers`, `provider_metadata[provider]`, `last_provider_used`) when OAuth callback completes. Integrate into both new user and existing user code paths within `handle_oauth_callback()`.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: pydantic (model validation), boto3 (DynamoDB), aws-xray-sdk (tracing)
**Storage**: DynamoDB (existing User table with federation fields)
**Testing**: pytest with moto mocks for DynamoDB
**Target Platform**: AWS Lambda
**Project Type**: Backend API Lambda functions
**Performance Goals**: No latency regression on OAuth callback
**Constraints**: Single DynamoDB update_item call for atomicity
**Scale/Scope**: All OAuth sign-ins (Google, GitHub providers)

## Constitution Check

- [x] No new dependencies added
- [x] No new infrastructure required
- [x] Single file modification (auth.py)
- [x] Follows existing error handling patterns (silent failure on metadata update)
- [x] Uses established DynamoDB update patterns

## Project Structure

### Documentation (this feature)

```text
specs/1169-oauth-populate-federation-fields/
├── spec.md                        # Feature specification
├── plan.md                        # This file
├── research.md                    # Code research output
├── checklists/
│   └── requirements.md            # Quality checklist
└── tasks.md                       # Implementation tasks (from /speckit.tasks)
```

### Source Code (repository root)

```text
src/lambdas/dashboard/auth.py      # Add _link_provider() helper + integrate
tests/unit/dashboard/test_auth.py  # Add test coverage
```

**Structure Decision**: Backend-only change. Single file modification with helper function following existing patterns.

## Research Summary

### Current OAuth Flow (handle_oauth_callback)

1. Exchange authorization code for tokens
2. Decode ID token to extract claims (sub, email, picture)
3. Check for existing user by email (GSI query)
4. Create new user OR update existing user with cognito_sub
5. **GAP**: Never populates linked_providers, provider_metadata, last_provider_used

### Available JWT Claims

| Claim | Field Mapping | Required |
|-------|--------------|----------|
| `sub` | `provider_metadata[provider].sub` | YES |
| `email` | `provider_metadata[provider].email` | NO |
| `picture` | `provider_metadata[provider].avatar` | NO |
| `email_verified` | Sets `provider_metadata[provider].verified_at` | NO |

### Existing Update Pattern (from _update_cognito_sub)

```python
table.update_item(
    Key={"PK": user.pk, "SK": user.sk},
    UpdateExpression="SET cognito_sub = :sub",
    ExpressionAttributeValues={":sub": cognito_sub},
)
```

## Implementation Design

### New Helper Function: `_link_provider()`

**Location**: After `_update_cognito_sub()` (line ~1646) in `auth.py`

**Signature**:
```python
def _link_provider(
    table: Any,
    user: User,
    provider: str,
    sub: str | None,
    email: str | None,
    avatar: str | None = None,
    email_verified: bool = False,
) -> None:
```

**Responsibilities**:
1. Build ProviderMetadata object from claims
2. Determine if provider already in linked_providers
3. Execute atomic DynamoDB update with:
   - SET provider_metadata.{provider} = :metadata
   - SET last_provider_used = :provider
   - SET linked_providers = list_append(linked_providers, :provider) if not present
4. Follow silent failure pattern (log warning, don't raise)

### Integration Points

1. **New User Creation** (line ~1603): Call after `_create_authenticated_user()`
2. **Existing User Update** (line ~1590): Call after `_update_cognito_sub()`

### DynamoDB Update Expression

```python
# Build update expression dynamically
update_expr_parts = [
    "SET provider_metadata.#provider = :metadata",
    "last_provider_used = :provider",
]
attr_names = {"#provider": provider}
attr_values = {
    ":metadata": metadata.model_dump(),
    ":provider": provider,
}

# Only add to linked_providers if not present (use list_append)
if provider not in user.linked_providers:
    update_expr_parts.append("linked_providers = list_append(if_not_exists(linked_providers, :empty), :new_provider)")
    attr_values[":empty"] = []
    attr_values[":new_provider"] = [provider]
```

## Error Handling

Follow `_update_cognito_sub()` pattern:
- Wrap in try/except
- Log warning on failure with sanitized user ID
- Don't raise - allow OAuth to succeed even if metadata update fails
- Authentication is primary; federation metadata is enhancement

## Test Plan

### Unit Tests (tests/unit/dashboard/test_auth.py)

1. `test_link_provider_new_user_google` - First OAuth with Google
2. `test_link_provider_new_user_github` - First OAuth with GitHub
3. `test_link_provider_existing_user_same_provider` - Re-auth with same provider
4. `test_link_provider_existing_user_add_provider` - Link second provider
5. `test_link_provider_no_duplicate_entries` - Verify no duplicates in linked_providers
6. `test_link_provider_handles_missing_avatar` - Avatar is optional
7. `test_link_provider_handles_missing_sub` - Sub required, should fail gracefully
8. `test_link_provider_silent_failure` - DynamoDB error doesn't break OAuth

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| DynamoDB update failure breaks OAuth | Silent failure pattern - log only |
| Race condition with concurrent logins | Use conditional updates where needed |
| Backward compatibility with legacy users | linked_providers defaults to empty list |

## Dependencies

- Feature 1162 (User Model Federation Fields) - COMPLETE
- Cognito ID token claims available - VERIFIED

## Out of Scope

- Role advancement (Feature 1170)
- Email verification marking (Feature 1171)
- Frontend display (Phase 2)
