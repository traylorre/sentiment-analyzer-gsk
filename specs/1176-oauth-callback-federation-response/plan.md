# Implementation Plan: OAuth Callback Federation Response

**Branch**: `1176-oauth-callback-federation-response` | **Date**: 2025-01-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1176-oauth-callback-federation-response/spec.md`

## Summary

Add four federation fields (`role`, `verification`, `linked_providers`, `last_provider_used`) to `OAuthCallbackResponse` model and populate them in the `handle_oauth_callback()` return path. This closes the gap where backend updates DynamoDB with federation data but doesn't return it to frontend.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: Pydantic (BaseModel), existing auth.py infrastructure
**Storage**: DynamoDB (already handled by existing helper functions)
**Testing**: pytest with moto mocks
**Target Platform**: AWS Lambda
**Project Type**: Web application (backend-only for this feature)
**Performance Goals**: No change - adding 4 fields to existing response
**Constraints**: Backward compatible - all new fields must be optional with defaults
**Scale/Scope**: Single file change (auth.py) + unit tests

## Constitution Check

_GATE: Must pass before implementation._

- [x] No quick fixes - full speckit workflow
- [x] No workspace file destruction
- [x] Backward compatible (additive fields only)
- [x] Unit tests required

## Project Structure

### Documentation (this feature)

```text
specs/1176-oauth-callback-federation-response/
├── spec.md              # Feature specification (done)
├── plan.md              # This file
├── tasks.md             # Implementation tasks
└── checklists/
    └── requirements.md  # Requirements checklist
```

### Source Code (repository root)

```text
src/lambdas/dashboard/
└── auth.py              # OAuthCallbackResponse model + handle_oauth_callback()

tests/unit/dashboard/
└── test_oauth_callback_federation.py  # New unit tests for federation fields
```

**Structure Decision**: Backend-only change. Single file modification + new test file.

## Implementation Approach

### Step 1: Extend OAuthCallbackResponse Model

Add 4 optional fields at lines 999-1017 in `auth.py`:

```python
class OAuthCallbackResponse(BaseModel):
    # ... existing fields ...

    # Federation fields (Feature 1176)
    role: str = "anonymous"
    verification: str = "none"
    linked_providers: list[str] = Field(default_factory=list)
    last_provider_used: str | None = None
```

### Step 2: Populate Fields in handle_oauth_callback()

At lines 1654-1668, after the helper functions have updated DynamoDB, the User object contains the updated federation state. Add federation fields to the return:

```python
return OAuthCallbackResponse(
    status="authenticated",
    email_masked=_mask_email(email),
    # ... existing fields ...

    # Federation fields from updated user
    role=user.role,
    verification=user.verification,
    linked_providers=user.linked_providers,
    last_provider_used=user.last_provider_used,
)
```

### Step 3: Unit Tests

Create `tests/unit/dashboard/test_oauth_callback_federation.py` with tests:
- Test federation fields present in successful OAuth response
- Test role advancement reflected in response
- Test verification marking reflected in response
- Test linked_providers updated in response
- Test defaults used for conflict/error responses

## Risk Assessment

- **Low Risk**: Additive change - new optional fields with defaults
- **No Security Impact**: Federation fields already validated in User model
- **No Database Changes**: Just returning existing data that's already stored
- **Backward Compatible**: Existing code ignores unknown fields

## Dependencies

- None. This is Phase 1 (Backend Non-Breaking). Does not depend on other features.
- Feature 1177 depends on this feature.
