# Quickstart: Email-to-OAuth Link (Flow 4)

**Feature**: 1182-email-to-oauth-link
**Date**: 2026-01-09

## Overview

This feature adds two functions to `src/lambdas/dashboard/auth.py`:

1. `link_email_to_oauth_user()` - Initiate email linking
2. `complete_email_link()` - Verify magic link and complete linking

## Implementation Checklist

### Step 1: Implement link_email_to_oauth_user()

**Location**: `src/lambdas/dashboard/auth.py`

```python
@xray_recorder.capture("link_email_to_oauth_user")
async def link_email_to_oauth_user(user: User, email: str) -> None:
    """
    Initiate email linking for OAuth user.

    1. Validate email not already linked
    2. Store pending_email on user record
    3. Generate magic link with user_id context
    4. Send verification email
    """
    # Implementation here
```

**Key Points**:
- Check `"email" not in user.linked_providers`
- Normalize email: `email.lower()`
- Update user record with `pending_email`
- Generate token with `user_id` claim
- Send magic link email

### Step 2: Implement complete_email_link()

**Location**: `src/lambdas/dashboard/auth.py`

```python
@xray_recorder.capture("complete_email_link")
async def complete_email_link(token: str, user: User) -> User:
    """
    Complete email linking after magic link verification.

    1. Verify token (not expired, not used, user_id matches)
    2. Add "email" to linked_providers
    3. Create provider_metadata entry
    4. Clear pending_email
    5. Log audit event
    """
    # Implementation here
```

**Key Points**:
- Verify token atomically (conditional write)
- Validate `token.user_id == user.user_id`
- Create `ProviderMetadata(email=..., linked_at=..., verified_at=...)`
- Log `AUTH_METHOD_LINKED` event

### Step 3: Add API Endpoints

**Location**: `src/lambdas/dashboard/router_v2.py`

```python
@router.post("/auth/link-email", status_code=202)
async def initiate_email_link(
    request: LinkEmailRequest,
    session: Session = Depends(get_current_session),
):
    user = await get_user(session.user_id)
    await link_email_to_oauth_user(user, request.email)
    return {"message": "Verification email sent"}

@router.post("/auth/complete-email-link")
async def complete_email_link_endpoint(
    request: CompleteEmailLinkRequest,
    session: Session = Depends(get_current_session),
):
    user = await get_user(session.user_id)
    updated_user = await complete_email_link(request.token, user)
    return {"message": "Email linked successfully", "linked_providers": updated_user.linked_providers}
```

### Step 4: Add Unit Tests

**Location**: `tests/unit/dashboard/test_email_to_oauth_link.py`

Test cases required:
1. Happy path: OAuth user links email successfully
2. Error: Email already linked
3. Error: Magic link expired
4. Error: Magic link already used
5. Error: Token user_id mismatch
6. State: pending_email set correctly during initiation
7. State: pending_email cleared after completion
8. Audit: AUTH_METHOD_LINKED event logged

## Running Tests

```bash
# Run Flow 4 tests only
MAGIC_LINK_SECRET="test-secret-key-at-least-32-characters" \
pytest tests/unit/dashboard/test_email_to_oauth_link.py -xvs

# Run all auth tests
MAGIC_LINK_SECRET="test-secret-key-at-least-32-characters" \
pytest tests/unit/dashboard/ -k "auth" -xvs
```

## Dependencies

No new dependencies required. Uses existing:
- `pydantic` for request/response models
- `boto3` for DynamoDB operations
- `PyJWT` for token generation/verification
- `aws-xray-sdk` for tracing
