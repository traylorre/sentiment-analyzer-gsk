# Data Model: Email-to-OAuth Link (Flow 4)

**Feature**: 1182-email-to-oauth-link
**Date**: 2026-01-09

## Entities

### User (Extended)

Uses existing User model with federation fields from Feature 1162.

| Field | Type | Description |
|-------|------|-------------|
| user_id | str | UUID primary identifier |
| pending_email | str \| None | Email awaiting magic link verification |
| linked_providers | list[str] | Providers linked to account (e.g., ["google", "email"]) |
| provider_metadata | dict[str, ProviderMetadata] | Per-provider details |
| primary_email | str \| None | Canonical verified email |
| verification | str | "none" \| "pending" \| "verified" |
| role | str | "anonymous" \| "free" \| "paid" \| "operator" |

### ProviderMetadata

| Field | Type | Description |
|-------|------|-------------|
| sub | str \| None | OAuth subject claim (provider user ID) |
| email | str \| None | Email from this provider |
| avatar | str \| None | Avatar URL |
| linked_at | datetime | When provider was linked |
| verified_at | datetime \| None | When email was verified (email provider only) |

### MagicLinkToken (Existing)

| Field | Type | Description |
|-------|------|-------------|
| token_id | str | UUID token identifier |
| email | str | Email address for verification |
| user_id | str \| None | User ID for Flow 4 linking (NEW) |
| created_at | datetime | Token creation time |
| expires_at | datetime | Token expiry time |
| used | bool | Whether token has been consumed |
| used_by_ip | str \| None | IP that consumed the token |

## State Transitions

### Email Linking Flow

```
OAuth User (no email linked)
    │
    ▼ link_email_to_oauth_user()
    │
    ├─ pending_email = email.lower()
    │
    ▼ (Magic link sent)
    │
Waiting for Verification
    │
    ▼ complete_email_link()
    │
    ├─ linked_providers += ["email"]
    ├─ provider_metadata["email"] = {...}
    ├─ pending_email = None
    ├─ verification = "verified"
    │
    ▼
OAuth User (email linked)
```

### Validation Rules

1. **Pre-link validation**: `"email" not in user.linked_providers`
2. **Token validation**: Token not expired, not used, user_id matches
3. **Post-link validation**: `"email" in user.linked_providers`, `pending_email is None`

## DynamoDB Schema

### User Record

```
PK: USER#{user_id}
SK: PROFILE
entity_type: USER
pending_email: "{email}" | null
linked_providers: ["google"] -> ["google", "email"]
provider_metadata: {
    "google": {...},
    "email": {
        "email": "user@example.com",
        "linked_at": "2026-01-09T22:00:00Z",
        "verified_at": "2026-01-09T22:05:00Z"
    }
}
```

### Magic Link Token Record

```
PK: TOKEN#{token_id}
SK: MAGIC_LINK
entity_type: MAGIC_LINK_TOKEN
email: "user@example.com"
user_id: "550e8400-e29b-41d4-a716-446655440000"  # NEW for Flow 4
created_at: "2026-01-09T22:00:00Z"
expires_at: "2026-01-09T22:30:00Z"
used: false
TTL: 1736460600  # expires_at as epoch
```
