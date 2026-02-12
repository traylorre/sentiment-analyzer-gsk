# Quickstart: Multi-User Session Consistency

**Feature**: 014-session-consistency
**Date**: 2025-12-01

## Overview

This guide provides the essential information needed to implement Feature 014. It covers the key patterns, code snippets, and testing approaches for session consistency improvements.

---

## Quick Reference

### Key Files to Modify

| File | Changes |
|------|---------|
| `src/lambdas/dashboard/auth.py` | Atomic token verification, hybrid headers |
| `src/lambdas/dashboard/router_v2.py` | Accept both X-User-ID and Bearer token |
| `src/lambdas/shared/models/user.py` | Add `revoked`, `merged_to` fields |
| `src/lambdas/shared/auth/merge.py` | Tombstone-based idempotent merge |
| `frontend/src/stores/auth-store.ts` | Auto-create session on mount |
| `infrastructure/terraform/modules/dynamodb/main.tf` | Add email GSI |

### New Files to Create

| File | Purpose |
|------|---------|
| `src/lambdas/shared/middleware/auth_middleware.py` | Hybrid header extraction |
| `src/lambdas/shared/errors/session_errors.py` | Session-specific exceptions |
| `frontend/src/hooks/use-session-init.ts` | Session initialization hook |
| `frontend/src/components/providers/session-provider.tsx` | App-level session provider |

---

## Implementation Patterns

### 1. Hybrid Auth Header Extraction (FR-001, FR-002)

```python
# src/lambdas/shared/middleware/auth_middleware.py

from fastapi import Request, HTTPException
from typing import Optional

def extract_user_id(request: Request) -> Optional[str]:
    """
    Extract user ID from either Authorization Bearer or X-User-ID header.
    Bearer token takes precedence (preferred for new code).
    """
    # Try Bearer token first (new standard)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # Validate token and extract user_id
        user_id = validate_access_token(token)
        if user_id:
            return user_id

    # Fall back to X-User-ID (legacy, backward compatible)
    user_id = request.headers.get("X-User-ID")
    if user_id:
        # Validate UUID format
        try:
            uuid.UUID(user_id)
            return user_id
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-User-ID format")

    return None
```

### 2. Auto-Create Session on App Load (FR-003)

```tsx
// frontend/src/components/providers/session-provider.tsx

'use client';

import { useEffect } from 'react';
import { useAuthStore } from '@/stores/auth-store';

interface SessionProviderProps {
  children: React.ReactNode;
}

export function SessionProvider({ children }: SessionProviderProps) {
  const { user, isLoading, signInAnonymous, isSessionValid } = useAuthStore();

  useEffect(() => {
    // Auto-create anonymous session if none exists
    const initSession = async () => {
      if (!user && !isLoading) {
        await signInAnonymous();
      } else if (user && !isSessionValid()) {
        // Session expired, create new one
        await signInAnonymous();
      }
    };

    initSession();
  }, [user, isLoading, signInAnonymous, isSessionValid]);

  return <>{children}</>;
}
```

```tsx
// frontend/src/app/layout.tsx - Wrap app with provider

import { SessionProvider } from '@/components/providers/session-provider';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <SessionProvider>
          {children}
        </SessionProvider>
      </body>
    </html>
  );
}
```

### 3. Atomic Magic Link Verification (FR-004, FR-005, FR-006)

```python
# src/lambdas/dashboard/auth.py

from botocore.exceptions import ClientError

def verify_and_consume_token(token_id: str, table) -> MagicLinkToken:
    """
    Atomically verify token is unused/unexpired and mark it used.

    This prevents race conditions where two concurrent requests
    could both successfully verify the same token.
    """
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
            # Token already used or expired - race condition handled!
            raise TokenAlreadyUsedOrExpiredError(token_id)
        raise
```

### 4. Email Uniqueness with GSI (FR-007, FR-008, FR-009)

```hcl
# infrastructure/terraform/modules/dynamodb/main.tf

resource "aws_dynamodb_table" "main" {
  # ... existing config ...

  # Email uniqueness GSI
  global_secondary_index {
    name               = "email-index"
    hash_key           = "email"
    range_key          = "entity_type"
    projection_type    = "KEYS_ONLY"
  }

  attribute {
    name = "email"
    type = "S"
  }

  attribute {
    name = "entity_type"
    type = "S"
  }
}
```

```python
# User creation with uniqueness check
def create_user_with_email(user: User, table) -> bool:
    """Create user with email uniqueness guarantee."""
    try:
        table.put_item(
            Item=user.to_dynamodb_item(),
            ConditionExpression="attribute_not_exists(PK)"
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            # Check if email already exists via GSI
            existing = get_user_by_email(user.email, table)
            if existing:
                raise EmailAlreadyExistsError(user.email)
        raise
```

### 5. Tombstone-Based Idempotent Merge (FR-013, FR-014, FR-015)

```python
# src/lambdas/shared/auth/merge.py

def merge_anonymous_to_authenticated(
    source_user_id: str,
    target_user_id: str,
    table
) -> MergeResult:
    """
    Idempotent merge using tombstone markers.

    Pattern:
    1. Mark source item with merged_to BEFORE copying
    2. Copy to target
    3. On retry, skip items already marked (idempotency)
    """
    items = query_user_items(source_user_id, table)
    merged_count = 0
    skipped_count = 0

    for item in items:
        # Skip already-merged items (idempotency)
        if item.get("merged_to"):
            skipped_count += 1
            continue

        # Step 1: Mark source with tombstone FIRST
        table.update_item(
            Key={"PK": item["PK"], "SK": item["SK"]},
            UpdateExpression="SET merged_to = :target, merged_at = :now",
            ExpressionAttributeValues={
                ":target": target_user_id,
                ":now": datetime.utcnow().isoformat()
            }
        )

        # Step 2: Copy to target (safe to retry)
        new_item = copy_item_to_user(item, target_user_id)
        new_item["original_user_id"] = source_user_id
        table.put_item(Item=new_item)
        merged_count += 1

    # Mark source user as merged
    table.update_item(
        Key={"PK": f"USER#{source_user_id}", "SK": "PROFILE"},
        UpdateExpression="SET merged_to = :target, merged_at = :now",
        ExpressionAttributeValues={
            ":target": target_user_id,
            ":now": datetime.utcnow().isoformat()
        }
    )

    return MergeResult(
        source_user_id=source_user_id,
        target_user_id=target_user_id,
        items_merged=merged_count,
        items_skipped=skipped_count
    )
```

### 6. Server-Side Session Revocation (FR-016, FR-017)

```python
# src/lambdas/shared/models/user.py

class User(BaseModel):
    # ... existing fields ...
    revoked: bool = False
    revoked_at: datetime | None = None
    revoked_reason: str | None = None

# Session validation with revocation check
def validate_session(user_id: str, table) -> User:
    """Validate session, checking for server-side revocation."""
    user = get_user(user_id, table)

    if user.revoked:
        raise SessionRevokedException(
            reason=user.revoked_reason,
            revoked_at=user.revoked_at
        )

    if user.session_expires_at < datetime.utcnow():
        raise SessionExpiredError(user_id)

    return user

# Bulk revocation for andon cord
def revoke_sessions_bulk(
    scope: str,
    reason: str,
    user_ids: list[str] | None,
    table
) -> int:
    """Revoke sessions for incident response."""
    revoked_count = 0

    if scope == "specific" and user_ids:
        for user_id in user_ids:
            revoke_user_session(user_id, reason, table)
            revoked_count += 1
    elif scope == "all":
        # Scan all users and revoke
        paginator = table.meta.client.get_paginator('scan')
        for page in paginator.paginate(
            TableName=table.name,
            FilterExpression="begins_with(PK, :prefix) AND SK = :profile",
            ExpressionAttributeValues={
                ":prefix": "USER#",
                ":profile": "PROFILE"
            }
        ):
            for item in page.get("Items", []):
                revoke_user_session(item["user_id"], reason, table)
                revoked_count += 1

    return revoked_count
```

---

## Testing Patterns

### Race Condition Test (pytest-asyncio)

```python
# tests/integration/test_session_race_conditions.py

import pytest
import asyncio
from httpx import AsyncClient

@pytest.mark.asyncio
@pytest.mark.session_consistency
@pytest.mark.session_us2
async def test_concurrent_magic_link_verification():
    """
    FR-005: Exactly one verification succeeds when concurrent requests race.
    """
    # Setup: Create a magic link token
    token = await create_test_magic_link("test@example.com")

    async with AsyncClient(base_url=API_URL) as client:
        # Fire 10 concurrent verification requests
        tasks = [
            client.post(
                "/api/v2/auth/magic-link/verify",
                json={"token": token.token_id, "signature": token.signature}
            )
            for _ in range(10)
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    # Assert exactly one success
    successes = [r for r in responses if hasattr(r, 'status_code') and r.status_code == 200]
    conflicts = [r for r in responses if hasattr(r, 'status_code') and r.status_code == 409]

    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
    assert len(conflicts) == 9, f"Expected 9 conflicts, got {len(conflicts)}"
```

### Email Uniqueness Test

```python
@pytest.mark.asyncio
@pytest.mark.session_consistency
@pytest.mark.session_us3
async def test_concurrent_user_creation_same_email():
    """
    FR-008: Database rejects second write for same email.
    """
    email = f"test-{uuid.uuid4()}@example.com"

    async with AsyncClient(base_url=API_URL) as client:
        # Fire 10 concurrent OAuth callback requests
        tasks = [
            client.post(
                "/api/v2/auth/oauth/callback",
                json={"provider": "google", "code": f"code-{i}", "email": email}
            )
            for i in range(10)
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    # Assert exactly one account created
    successes = [r for r in responses if hasattr(r, 'status_code') and r.status_code == 200]
    conflicts = [r for r in responses if hasattr(r, 'status_code') and r.status_code == 409]

    assert len(successes) == 1, "Exactly one account should be created"
    assert len(conflicts) == 9, "Others should get conflict"
```

### Idempotent Merge Test

```python
@pytest.mark.session_consistency
@pytest.mark.session_us5
def test_merge_idempotency_on_retry(mock_dynamodb_table):
    """
    FR-014: Merge retries skip items already marked with merged_to.
    """
    # Setup: Create anonymous user with 3 configs
    anon_user_id = str(uuid.uuid4())
    auth_user_id = str(uuid.uuid4())
    setup_anonymous_user_with_configs(mock_dynamodb_table, anon_user_id, count=3)

    # First merge
    result1 = merge_anonymous_to_authenticated(anon_user_id, auth_user_id, mock_dynamodb_table)
    assert result1.items_merged == 3
    assert result1.items_skipped == 0

    # Second merge (retry) - should skip all
    result2 = merge_anonymous_to_authenticated(anon_user_id, auth_user_id, mock_dynamodb_table)
    assert result2.items_merged == 0
    assert result2.items_skipped == 3

    # Verify no duplicates in target
    target_configs = query_user_configs(auth_user_id, mock_dynamodb_table)
    assert len(target_configs) == 3
```

---

## Pytest Markers

Add to `pytest.ini`:

```ini
[pytest]
markers =
    # ... existing markers ...
    session_consistency: Feature 014 - Session consistency tests
    session_us1: User Story 1 - Consistent session across tabs
    session_us2: User Story 2 - Concurrent magic link verification
    session_us3: User Story 3 - Email uniqueness guarantee
    session_us4: User Story 4 - Session refresh
    session_us5: User Story 5 - Atomic account merge
    session_us6: User Story 6 - Fast email lookup
```

---

## Migration Checklist

Before deployment:

1. [ ] Deploy email GSI via Terraform (wait for ACTIVE status)
2. [ ] Run migration script to add `revoked=false` and `entity_type="USER"` to existing users
3. [ ] Verify GSI is populated with existing email records
4. [ ] Deploy backend changes
5. [ ] Deploy frontend changes
6. [ ] Verify anonymous session auto-creation in browser
7. [ ] Run E2E test suite against preprod

---

## Error Codes Reference

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `TOKEN_ALREADY_USED` | 409 | Magic link token already verified |
| `TOKEN_EXPIRED` | 410 | Magic link token expired |
| `EMAIL_EXISTS` | 409 | Email already registered |
| `SESSION_REVOKED` | 403 | Session revoked server-side |
| `SESSION_EXPIRED` | 401 | Session expired |
| `MERGE_CONFLICT` | 409 | Source account already merged |
| `INVALID_MERGE_TARGET` | 400 | Merge target doesn't exist |

---

## Performance Expectations

| Operation | Target | Measured By |
|-----------|--------|-------------|
| Anonymous session creation | <500ms p90 | X-Ray trace duration |
| Email lookup (GSI) | <100ms | GSI query latency |
| Magic link verification | <500ms p90 | X-Ray trace duration |
| Account merge (5 items) | <2s | X-Ray trace duration |
| Bulk revocation (1000 users) | <30s | CloudWatch metric |
