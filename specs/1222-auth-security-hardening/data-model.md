# Data Model: Auth Security Hardening (1222)

## Entity Changes

### OAuth State Record (Modified)

**Table**: `{env}-sentiment-users`
**Key**: PK=`OAUTH_STATE#{state_id}`, SK=`STATE`

| Field | Type | Status | Description |
|-------|------|--------|-------------|
| state_id | String | Existing | 43-char URL-safe base64 (256 bits entropy) |
| provider | String | Existing | "google" or "github" |
| redirect_uri | String | Existing | Expected callback URI |
| created_at | String | Existing | ISO 8601 timestamp |
| used | Boolean | Existing | Whether state has been consumed |
| user_id | String | Existing | Optional anonymous user ID to link |
| ttl | Number | Existing | Unix epoch for 5-minute auto-expiry |
| **code_verifier** | **String** | **NEW** | PKCE code_verifier (43-128 chars, URL-safe base64) |

**State transitions** (unchanged):
- Created → `used=false`, `ttl=now+300s`
- Consumed → `used=true` (conditional update: `used = :false`)
- Expired → auto-deleted by DynamoDB TTL

### User Record (Unchanged schema, new write guards)

**Table**: `{env}-sentiment-users`
**Key**: PK=`USER#{user_id}`, SK=`PROFILE`

No new fields added. Existing fields affected by conditional write guards:

| Field | Guard Added | Description |
|-------|-------------|-------------|
| verification | ConditionExpression | Prevents setting `verified` without valid verification flow |
| provider_sub | Pre-check query | GSI lookup before update to prevent duplicate linking |
| provider_metadata | No change | Updated during provider linking (existing behavior) |

### GSI: by_provider_sub (Unchanged)

| Attribute | Role | Type |
|-----------|------|------|
| provider_sub | Hash Key | String (format: `{provider}:{sub}`) |
| (none) | Range Key | N/A |
| Projection | ALL | Full item |

**Usage change**: Previously read-only for login lookup. Now also queried during provider linking to enforce uniqueness (FR-001, FR-002).

## Validation Rules

### Provider Sub Uniqueness
- `provider_sub` must be globally unique across all user records
- Format: `{provider}:{sub}` (e.g., `google:118368473829470293847`)
- Enforced by: GSI query pre-check + application-level rejection
- Race condition window: GSI eventual consistency (~100ms) — acceptable for this write pattern

### Verification State Transitions (Data Layer)
- `none → verified`: Only via `_mark_email_verified()` or `complete_email_link()` with conditional write
- `verified → none`: Blocked (ConditionExpression prevents downgrade)
- `none → pending → verified`: Full flow via magic link (pending set on link request, verified on consumption)

### Account Merge Authorization
- `current_user_id` must match the authenticated JWT `sub` claim
- `link_to_user_id` must be a different, existing user
- Both users must exist and be accessible to the caller
- Merge is idempotent (tombstone check prevents double-merge)
