# Data Model: OAuth Auto-Link

## Entities

### User (existing, no changes)

The User entity already has all required fields from previous features:

| Field | Type | Description |
|-------|------|-------------|
| user_id | string | Primary key (UUID) |
| email | string | Primary email address |
| role | enum | "anonymous" \| "free" \| "paid" \| "operator" |
| verification | enum | "none" \| "pending" \| "verified" |
| auth_type | string | Primary auth method ("anonymous", "email", "google", "github") |
| linked_providers | list[string] | All linked auth methods |
| provider_sub | string | Current provider's subject claim (format: "{provider}:{sub}") |
| provider_metadata | dict | Per-provider metadata (sub, email, avatar, linked_at) |
| last_provider_used | string | Most recently used provider (for avatar selection) |

### OAuthClaims (input from OAuth provider)

| Field | Type | Description |
|-------|------|-------------|
| sub | string | OAuth provider's unique user ID |
| email | string | Email from OAuth provider |
| email_verified | boolean | Whether provider verified the email |
| name | string | Display name |
| picture | string | Avatar URL |

### ProviderMetadata (stored per provider in user.provider_metadata)

| Field | Type | Description |
|-------|------|-------------|
| sub | string | Provider's unique user ID |
| email | string | Email from this provider |
| avatar | string | Avatar URL |
| linked_at | datetime | When this provider was linked |

## State Transitions

### Linking Flow

```
User State: free:email, verified
           │
           ▼
    OAuth Callback
           │
           ▼
┌──────────────────────────┐
│ can_auto_link_oauth()    │
│ - Check email_verified   │
│ - Check domain match     │
│ - Check duplicate sub    │
└──────────────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
  AUTO         MANUAL
    │             │
    ▼             ▼
link_oauth   Show Prompt
    │         │
    │    ┌────┴────┐
    │    │         │
    │    ▼         ▼
    │  [Link]   [Separate]
    │    │         │
    ▼    ▼         ▼
 LINKED        NEW SESSION
(linked_providers += provider)
```

## No Schema Changes

This feature requires no DynamoDB schema changes. All required attributes and GSIs already exist:
- User attributes: linked_providers, provider_sub, provider_metadata (Feature 1180)
- GSI: by_provider_sub (Feature 1180)
