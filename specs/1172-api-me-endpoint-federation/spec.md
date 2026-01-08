# Feature 1172: API /me Endpoint Federation Fields

## Problem Statement

The `/api/v2/auth/me` endpoint currently returns minimal user info (`auth_type`, `email_masked`, `configs_count`, `max_configs`, `session_expires_in_seconds`). It's missing federation fields needed for frontend RBAC-aware UI decisions:

- `role`: Authorization tier (anonymous/free/paid/operator)
- `linked_providers`: List of connected auth providers
- `verification`: Email verification status (none/pending/verified)
- `last_provider_used`: Most recent auth provider (for avatar selection)

Without these fields, the frontend cannot:
- Display role-specific UI elements
- Show which providers are linked
- Gate features based on verification status
- Select the correct avatar from linked providers

## Root Cause

Feature 1162 added federation fields to the User model, but the `/api/v2/auth/me` response model (`UserMeResponse`) was not updated to include them. The fields exist in the backend but aren't exposed to the frontend.

## Solution

Extend `UserMeResponse` to include non-sensitive federation fields:

1. **Add fields to response model** (response_models.py)
2. **Extract from User in handler** (router_v2.py)
3. **Update tests** to verify new fields

## Technical Specification

### Response Model Changes

**File:** `src/lambdas/shared/response_models.py`

```python
class UserMeResponse(BaseModel):
    """Minimal /api/v2/auth/me response - only what frontend needs."""

    auth_type: str  # anonymous, email, google, github
    email_masked: str | None = None  # j***@example.com
    configs_count: int
    max_configs: int = 2
    session_expires_in_seconds: int | None = None
    # NEW: Federation fields (Feature 1172)
    role: str = "anonymous"  # anonymous, free, paid, operator
    linked_providers: list[str] = Field(default_factory=list)  # ["google", "github"]
    verification: str = "none"  # none, pending, verified
    last_provider_used: str | None = None  # Most recent provider
```

### Handler Changes

**File:** `src/lambdas/dashboard/router_v2.py`

```python
response = UserMeResponse(
    auth_type=user.auth_type,
    email_masked=mask_email(user.email),
    configs_count=config_count,
    max_configs=2,
    session_expires_in_seconds=seconds_until(user.session_expires_at),
    # NEW: Federation fields (Feature 1172)
    role=user.role,
    linked_providers=user.linked_providers,
    verification=user.verification,
    last_provider_used=user.last_provider_used,
)
```

### Security Analysis

| Field | Sensitivity | Justification |
|-------|-------------|---------------|
| `role` | Low | Authorization tier, needed for RBAC UI |
| `linked_providers` | Low | Already in SessionInfoMinimalResponse |
| `verification` | Low | Status indicator, no PII |
| `last_provider_used` | Low | Provider name only, no OAuth tokens |

None of these fields expose:
- Internal IDs (user_id, cognito_sub)
- OAuth secrets or tokens
- Unmasked emails
- Timestamps that could enable timing attacks

## Acceptance Criteria

1. `/api/v2/auth/me` response includes `role` field
2. Response includes `linked_providers` list
3. Response includes `verification` status
4. Response includes `last_provider_used` (nullable)
5. Existing fields (`auth_type`, `email_masked`, etc.) unchanged
6. Unit tests verify all new fields
7. OpenAPI schema updated automatically via pydantic

## Out of Scope

- Frontend consumption of these fields (Feature 1173, 1174)
- Role-based access control in backend (separate feature)
- Changing existing field types or names

## Dependencies

- **Requires:** Features 1169-1171 (backend federation fields) - MERGED
- **Blocks:** Feature 1173 (frontend User type), Feature 1174 (frontend auth store)

## Testing Strategy

### Unit Tests

1. `test_me_response_includes_role` - Verify role field in response
2. `test_me_response_includes_linked_providers` - Verify list field
3. `test_me_response_includes_verification` - Verify status field
4. `test_me_response_includes_last_provider` - Verify nullable field
5. `test_me_response_backward_compatible` - Existing fields unchanged

### Test Pattern

Follow existing `/api/v2/auth/me` test patterns in:
`tests/unit/dashboard/test_router_v2.py`

## References

- Feature 1162: User Model Federation Fields
- `src/lambdas/dashboard/router_v2.py:1890-1926` (endpoint)
- `src/lambdas/shared/response_models.py:50-58` (model)
- `src/lambdas/shared/response_models.py:116-123` (similar pattern)
