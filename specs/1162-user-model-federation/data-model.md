# Data Model: User Model Federation Fields

**Feature**: 1162-user-model-federation
**Created**: 2026-01-07
**Canonical Source**: `specs/1126-auth-httponly-migration/spec-v2.md` (lines 4168-4196)

## Entities

### ProviderMetadata (NEW)

Stores per-provider OAuth data for federated authentication.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `sub` | `str \| None` | No | `None` | OAuth subject claim (provider's user ID) |
| `email` | `str \| None` | No | `None` | Email address from this provider |
| `avatar` | `str \| None` | No | `None` | Avatar URL from provider |
| `linked_at` | `datetime` | Yes | - | When provider was linked to account |
| `verified_at` | `datetime \| None` | No | `None` | For email provider: when email was verified |

**Notes**:
- `sub` is the OAuth 2.0 "sub" claim - the unique identifier the provider uses
- `linked_at` is required and set when the provider is first linked
- `verified_at` only applies to email provider (magic link verification)

### User (MODIFIED)

Core identity model with new federation fields.

#### New Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `role` | `Literal["anonymous", "free", "paid", "operator"]` | Yes | `"anonymous"` | User authorization tier |
| `verification` | `Literal["none", "pending", "verified"]` | Yes | `"none"` | Email verification state |
| `pending_email` | `str \| None` | No | `None` | Email awaiting verification |
| `primary_email` | `str \| None` | No | `None` | Verified canonical email (alias: `email`) |
| `linked_providers` | `list[Literal["email", "google", "github"]]` | Yes | `[]` | List of linked auth providers |
| `provider_metadata` | `dict[str, ProviderMetadata]` | Yes | `{}` | Metadata per provider |
| `last_provider_used` | `Literal["email", "google", "github"] \| None` | No | `None` | Most recent auth provider |
| `role_assigned_at` | `datetime \| None` | No | `None` | When role was last changed |
| `role_assigned_by` | `str \| None` | No | `None` | Who changed the role |

#### Existing Fields (Retained)

| Field | Type | Status |
|-------|------|--------|
| `user_id` | `str` | Unchanged |
| `email` | `EmailStr \| None` | ALIAS → `primary_email` |
| `cognito_sub` | `str \| None` | Unchanged |
| `auth_type` | `Literal["anonymous", "email", "google", "github"]` | DEPRECATED |
| `created_at` | `datetime` | Unchanged |
| `last_active_at` | `datetime` | Unchanged |
| `session_expires_at` | `datetime` | Unchanged |
| `timezone` | `str` | Unchanged |
| `email_notifications_enabled` | `bool` | Unchanged |
| `daily_email_count` | `int` | Unchanged |
| `entity_type` | `str` | Unchanged |
| `revoked` | `bool` | Unchanged |
| `revoked_at` | `datetime \| None` | Unchanged |
| `revoked_reason` | `str \| None` | Unchanged |
| `merged_to` | `str \| None` | Unchanged |
| `merged_at` | `datetime \| None` | Unchanged |
| `subscription_active` | `bool` | Unchanged |
| `subscription_expires_at` | `datetime \| None` | Unchanged |
| `is_operator` | `bool` | DEPRECATED (use `role == "operator"`) |

## Relationships

```
User 1:N ProviderMetadata (embedded in provider_metadata dict)
```

The `provider_metadata` dictionary key is the provider name (`"email"`, `"google"`, `"github"`).

## Validation Rules

### Field-Level Validation

1. `role` must be one of: `"anonymous"`, `"free"`, `"paid"`, `"operator"`
2. `verification` must be one of: `"none"`, `"pending"`, `"verified"`
3. `linked_providers` items must be one of: `"email"`, `"google"`, `"github"`
4. `provider_metadata` keys must match `linked_providers` items
5. `last_provider_used` must be in `linked_providers` or `None`
6. `role_assigned_by` format: `"stripe_webhook"` or `"admin:{user_id}"`

### Cross-Field Validation (Feature 1163)

Deferred to Feature 1163 (Role-Verification Invariant):
- `anonymous` role cannot have `verification: "verified"`
- Non-anonymous roles must have `verification: "verified"`

## State Transitions

### Role Transitions

```
anonymous → free (on email verification)
anonymous → paid (not allowed - must verify first)
free → paid (on subscription purchase)
paid → free (on subscription expiry)
any → operator (admin assignment only)
```

### Verification Transitions

```
none → pending (email submitted)
pending → verified (email confirmed)
verified → pending (new email submitted)
```

## DynamoDB Storage

No schema migration required (NoSQL flexibility). New fields stored as top-level attributes:

```json
{
  "user_id": "usr_abc123",
  "role": "free",
  "verification": "verified",
  "pending_email": null,
  "primary_email": "user@example.com",
  "linked_providers": ["email", "google"],
  "provider_metadata": {
    "email": {
      "sub": null,
      "email": "user@example.com",
      "avatar": null,
      "linked_at": "2026-01-07T10:00:00Z",
      "verified_at": "2026-01-07T10:05:00Z"
    },
    "google": {
      "sub": "google-oauth-sub-123",
      "email": "user@gmail.com",
      "avatar": "https://lh3.googleusercontent.com/...",
      "linked_at": "2026-01-07T11:00:00Z",
      "verified_at": null
    }
  },
  "last_provider_used": "google",
  "role_assigned_at": "2026-01-07T10:05:00Z",
  "role_assigned_by": "stripe_webhook",
  "auth_type": "google",
  "is_operator": false,
  ...existing fields...
}
```

## Backward Compatibility

1. **Existing records without new fields**: Load with defaults
2. **`email` field access**: Aliased to `primary_email` for serialization
3. **`auth_type` field**: Retained for legacy code, deprecated
4. **`is_operator` field**: Retained, but `role == "operator"` is authoritative
