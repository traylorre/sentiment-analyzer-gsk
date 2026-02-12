# Data Model: Multi-User Session Consistency

**Feature**: 014-session-consistency
**Date**: 2025-12-01
**Status**: Complete

## Entity Overview

This feature modifies existing entities and adds new fields to support session consistency, atomic operations, and server-side revocation.

---

## 1. User Entity (Modified)

**Location**: `src/lambdas/shared/models/user.py`

### Current Schema
```python
class User(BaseModel):
    user_id: str                    # UUID, primary identifier
    email: str | None               # Email (authenticated users only)
    cognito_sub: str | None         # Cognito subject ID (OAuth users)
    auth_type: AuthType             # anonymous | email | google | github
    session_expires_at: datetime    # Session expiry timestamp
    last_active_at: datetime        # Last activity timestamp
    timezone: str                   # User timezone
    ttl: int                        # DynamoDB TTL for cleanup
```

### New Fields (Feature 014)
```python
class User(BaseModel):
    # ... existing fields ...

    # Session Revocation (FR-016, FR-017)
    revoked: bool = False                    # Server-side session invalidation flag
    revoked_at: datetime | None = None       # When session was revoked
    revoked_reason: str | None = None        # Reason for revocation (incident ID, admin action, etc.)

    # Email Uniqueness (FR-007, FR-008)
    # email field now indexed via GSI for atomic uniqueness checks
    # No schema change needed, but GSI must be created

    # Merge Tracking (FR-013, FR-014, FR-015)
    merged_to: str | None = None             # Target user ID if this account was merged
    merged_at: datetime | None = None        # When merge occurred
```

### DynamoDB Key Design
```
Primary Key:
  PK: USER#{user_id}
  SK: PROFILE

GSI: email-index (NEW)
  PK: email
  SK: entity_type
  Projection: KEYS_ONLY

Attributes:
  - user_id (S)
  - email (S, sparse - only for authenticated users)
  - cognito_sub (S)
  - auth_type (S)
  - session_expires_at (S, ISO8601)
  - last_active_at (S, ISO8601)
  - timezone (S)
  - ttl (N)
  - revoked (BOOL)
  - revoked_at (S, ISO8601)
  - revoked_reason (S)
  - merged_to (S)
  - merged_at (S, ISO8601)
  - entity_type (S) = "USER" (for GSI sort key)
```

### Validation Rules
| Field | Rule | Error |
|-------|------|-------|
| `user_id` | UUID v4 format | `InvalidUserIdError` |
| `email` | RFC 5322 email format (when present) | `InvalidEmailError` |
| `revoked_reason` | Max 500 characters | `ValidationError` |
| `merged_to` | Must be valid existing user_id | `InvalidMergeTargetError` |

### State Transitions
```
Anonymous User States:
  ACTIVE → REVOKED (via server-side revocation)
  ACTIVE → MERGED (via account merge)
  ACTIVE → EXPIRED (via TTL)

Authenticated User States:
  ACTIVE → REVOKED (via server-side revocation)
  ACTIVE → EXPIRED (via TTL, 90 days inactive)
```

---

## 2. MagicLinkToken Entity (Modified)

**Location**: `src/lambdas/shared/models/magic_link_token.py`

### Current Schema
```python
class MagicLinkToken(BaseModel):
    token_id: str                   # UUID, primary identifier
    email: str                      # Target email address
    signature: str                  # HMAC-SHA256 signature
    created_at: datetime            # Token creation time
    expires_at: datetime            # Token expiry (1 hour)
    used: bool                      # Whether token has been verified
    ttl: int                        # DynamoDB TTL
    anonymous_user_id: str | None   # Associated anonymous user for merge
```

### New Fields (Feature 014)
```python
class MagicLinkToken(BaseModel):
    # ... existing fields ...

    # Atomic Verification (FR-004, FR-005, FR-006)
    used_at: datetime | None = None         # Exact time of verification
    used_by_ip: str | None = None           # IP address that verified (audit)
    verification_attempt_count: int = 0     # Track failed attempts
```

### DynamoDB Key Design
```
Primary Key:
  PK: TOKEN#{token_id}
  SK: MAGIC_LINK

Attributes:
  - token_id (S)
  - email (S)
  - signature (S)
  - created_at (S, ISO8601)
  - expires_at (S, ISO8601)
  - used (BOOL)
  - used_at (S, ISO8601)
  - used_by_ip (S)
  - verification_attempt_count (N)
  - ttl (N)
  - anonymous_user_id (S)
```

### Validation Rules
| Field | Rule | Error |
|-------|------|-------|
| `token_id` | UUID v4 format | `InvalidTokenError` |
| `email` | RFC 5322 email format | `InvalidEmailError` |
| `signature` | 64-character hex string (SHA256) | `InvalidSignatureError` |
| `expires_at` | Must be > created_at | `InvalidExpiryError` |
| `used_by_ip` | Valid IPv4/IPv6 | `InvalidIPError` |

### Atomic Verification Condition
```python
# ConditionExpression for atomic verify-and-consume
ConditionExpression = "used = :false AND expires_at > :now"
UpdateExpression = "SET used = :true, used_at = :now, used_by_ip = :ip"
```

---

## 3. Configuration Entity (Modified for Merge)

**Location**: `src/lambdas/shared/models/configuration.py`

### Existing Schema (no changes to structure)
```python
class Configuration(BaseModel):
    config_id: str
    user_id: str
    name: str
    tickers: list[TickerConfig]
    # ... other fields
```

### New Fields (Feature 014)
```python
class Configuration(BaseModel):
    # ... existing fields ...

    # Merge Tracking (FR-013, FR-014, FR-015)
    merged_to: str | None = None             # Target config ID after merge
    merged_at: datetime | None = None        # When this config was merged
    original_user_id: str | None = None      # Original owner before merge
```

### DynamoDB Key Design
```
Primary Key:
  PK: USER#{user_id}
  SK: CONFIG#{config_id}

Merge Tombstone Pattern:
  When merged:
    - Source item: merged_to = target_config_id, merged_at = timestamp
    - Target item: original_user_id = source_user_id (if preserving lineage)
```

---

## 4. Session Token Entity (Conceptual - Frontend)

**Location**: `frontend/src/stores/auth-store.ts`

### TypeScript Interface
```typescript
interface SessionState {
  // User identity
  user: {
    userId: string;
    email: string | null;
    authType: 'anonymous' | 'email' | 'google' | 'github';
  } | null;

  // Token storage
  tokens: {
    accessToken: string;
    refreshToken?: string;  // HttpOnly cookie, not in JS
  } | null;

  // Session metadata
  sessionExpiresAt: string | null;  // ISO8601
  isAuthenticated: boolean;
  isAnonymous: boolean;

  // NEW: Session validity tracking (Feature 014)
  sessionCreatedAt: string | null;  // When session was created
  lastSyncedAt: string | null;      // Last backend sync timestamp
}
```

### localStorage Schema
```json
{
  "state": {
    "user": {
      "userId": "uuid-v4",
      "email": null,
      "authType": "anonymous"
    },
    "tokens": {
      "accessToken": "jwt-token"
    },
    "sessionExpiresAt": "2025-01-01T00:00:00Z",
    "isAuthenticated": false,
    "isAnonymous": true,
    "sessionCreatedAt": "2025-12-01T00:00:00Z",
    "lastSyncedAt": "2025-12-01T00:05:00Z"
  },
  "version": 1
}
```

---

## 5. Error Types (New)

**Location**: `src/lambdas/shared/errors/session_errors.py` (new file)

```python
class SessionError(Exception):
    """Base class for session-related errors."""
    pass

class SessionRevokedException(SessionError):
    """Session has been revoked server-side."""
    def __init__(self, reason: str | None = None):
        self.reason = reason
        super().__init__(f"Session revoked: {reason or 'No reason provided'}")

class TokenAlreadyUsedError(SessionError):
    """Magic link token has already been used."""
    pass

class TokenExpiredError(SessionError):
    """Magic link token has expired."""
    pass

class EmailAlreadyExistsError(SessionError):
    """Email address is already registered."""
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Email already registered: {email}")

class MergeConflictError(SessionError):
    """Account merge conflict detected."""
    def __init__(self, source_id: str, target_id: str, reason: str):
        self.source_id = source_id
        self.target_id = target_id
        self.reason = reason
        super().__init__(f"Merge conflict: {reason}")

class InvalidMergeTargetError(SessionError):
    """Merge target user does not exist or is invalid."""
    pass
```

---

## 6. GSI: email-index (New Infrastructure)

**Location**: `infrastructure/terraform/modules/dynamodb/main.tf`

### Terraform Definition
```hcl
resource "aws_dynamodb_table" "main" {
  # ... existing configuration ...

  # NEW: Email uniqueness GSI
  global_secondary_index {
    name               = "email-index"
    hash_key           = "email"
    range_key          = "entity_type"
    projection_type    = "KEYS_ONLY"

    # On-demand capacity (matches table)
    # No explicit read/write capacity needed
  }

  # Ensure email attribute is defined
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

### GSI Query Pattern
```python
def get_user_by_email(email: str, table) -> User | None:
    """O(1) email lookup via GSI."""
    response = table.query(
        IndexName="email-index",
        KeyConditionExpression="email = :email AND entity_type = :type",
        ExpressionAttributeValues={
            ":email": email,
            ":type": "USER"
        },
        Limit=1
    )
    items = response.get("Items", [])
    if not items:
        return None
    # Fetch full user record using PK from GSI result
    return get_user(items[0]["user_id"], table)
```

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           DynamoDB Table                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐        ┌─────────────────┐                    │
│  │      User       │        │  MagicLinkToken │                    │
│  ├─────────────────┤        ├─────────────────┤                    │
│  │ PK: USER#{id}   │        │ PK: TOKEN#{id}  │                    │
│  │ SK: PROFILE     │        │ SK: MAGIC_LINK  │                    │
│  │                 │        │                 │                    │
│  │ user_id         │◄───────│ anonymous_user_id                    │
│  │ email ──────────┼──GSI───│ email           │                    │
│  │ auth_type       │        │ used            │                    │
│  │ revoked (NEW)   │        │ used_at (NEW)   │                    │
│  │ merged_to (NEW) │        │ used_by_ip (NEW)│                    │
│  └────────┬────────┘        └─────────────────┘                    │
│           │                                                         │
│           │ 1:N                                                     │
│           ▼                                                         │
│  ┌─────────────────┐                                               │
│  │  Configuration  │                                               │
│  ├─────────────────┤                                               │
│  │ PK: USER#{id}   │                                               │
│  │ SK: CONFIG#{id} │                                               │
│  │                 │                                               │
│  │ config_id       │                                               │
│  │ merged_to (NEW) │                                               │
│  │ merged_at (NEW) │                                               │
│  └─────────────────┘                                               │
│                                                                     │
│  GSI: email-index                                                  │
│  ┌─────────────────┐                                               │
│  │ PK: email       │                                               │
│  │ SK: entity_type │                                               │
│  │ Projection: KEYS│                                               │
│  └─────────────────┘                                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Migration Requirements

### Existing Data Migration
1. **Add `revoked` field**: Set `revoked=false` for all existing users
2. **Add `entity_type` field**: Set `entity_type="USER"` for all user records (required for GSI)
3. **GSI backfill**: DynamoDB will automatically index existing items with `email` attribute

### Migration Script (to be created)
```python
def migrate_users_for_014(table):
    """Add new fields to existing user records."""
    paginator = table.meta.client.get_paginator('scan')

    for page in paginator.paginate(
        TableName=table.name,
        FilterExpression="begins_with(PK, :user_prefix)",
        ExpressionAttributeValues={":user_prefix": "USER#"}
    ):
        for item in page.get("Items", []):
            table.update_item(
                Key={"PK": item["PK"], "SK": item["SK"]},
                UpdateExpression="SET revoked = :false, entity_type = :user_type",
                ExpressionAttributeValues={
                    ":false": False,
                    ":user_type": "USER"
                },
                ConditionExpression="attribute_not_exists(revoked)"
            )
```

---

## Backward Compatibility

| Change | Impact | Mitigation |
|--------|--------|------------|
| New `revoked` field | None - defaults to `false` | Existing sessions continue working |
| New `merged_to` field | None - optional field | No impact on existing queries |
| Email GSI | None - additive change | Existing queries unaffected |
| New error types | API responses may change | Document new error codes |

All changes are additive. No existing functionality is modified or removed.
