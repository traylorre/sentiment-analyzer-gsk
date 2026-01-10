# Implementation Plan: OAuth State Validation

**Branch**: `1185-oauth-state-validation` | **Date**: 2026-01-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1185-oauth-state-validation/spec.md`

## Summary

Implement OAuth state parameter generation, storage, and validation to prevent redirect attacks (A12) and provider confusion attacks (A13). State will be stored in DynamoDB with TTL for automatic cleanup.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: boto3 (DynamoDB), secrets (stdlib)
**Storage**: DynamoDB (existing Users table)
**Testing**: pytest, moto (DynamoDB mocking)
**Target Platform**: AWS Lambda
**Project Type**: Web application (backend)
**Performance Goals**: State validation adds <50ms to OAuth callback latency
**Constraints**: State must be cryptographically secure, one-time use, expire after 5 minutes
**Scale/Scope**: ~4 files changed, ~200 lines of code

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security & Access Control | PASS | Implementing security feature per A12-A13 |
| Data & Model Requirements | PASS | State data is ephemeral, TTL cleanup |
| NoSQL/Expression safety | PASS | Will use ExpressionAttributeValues |
| IAM least-privilege | PASS | Lambda already has DynamoDB access |

No violations.

## Project Structure

### Documentation (this feature)

```text
specs/1185-oauth-state-validation/
├── spec.md
├── plan.md
├── research.md
├── tasks.md
└── checklists/
    └── requirements.md
```

### Source Code (affected files)

```text
src/lambdas/shared/auth/
├── oauth_state.py       # NEW: OAuthState model and storage

src/lambdas/dashboard/
├── auth.py              # UPDATE: get_oauth_urls(), handle_oauth_callback()
├── router_v2.py         # UPDATE: Add state to request/response models

tests/unit/
├── dashboard/
│   └── test_oauth_state.py  # NEW: Unit tests for state validation
```

## Complexity Tracking

No violations to justify.

---

## Phase 0: Research

### Decision 1: State Storage Location
- **Decision**: Store in DynamoDB Users table with PK=`OAUTH_STATE#{state_id}`, SK=`STATE`
- **Rationale**: Reuse existing table, GSI not needed, TTL already configured
- **Alternative rejected**: Separate table would require new Terraform

### Decision 2: State Format
- **Decision**: `secrets.token_urlsafe(32)` = 43 characters URL-safe base64
- **Rationale**: 256 bits of entropy, no encoding issues in URLs
- **Alternative rejected**: UUID4 (128 bits) is less secure

### Decision 3: Expiry Handling
- **Decision**: DynamoDB TTL with 5 minute expiry, plus application-side check
- **Rationale**: TTL provides eventual cleanup, app check ensures immediate expiry enforcement
- **Alternative rejected**: Redis (adds infrastructure complexity)

## Phase 1: Design

### OAuthState Model

```python
@dataclass
class OAuthState:
    state_id: str           # PK: OAUTH_STATE#{state_id}
    provider: str           # "google" | "github"
    redirect_uri: str       # Expected callback URI
    created_at: datetime    # For expiry check
    user_id: str | None     # Optional anonymous user to link
    used: bool = False      # One-time use flag
    ttl: int                # DynamoDB TTL (Unix timestamp)
```

### DynamoDB Schema

```
PK: OAUTH_STATE#{state_id}
SK: STATE
GSI: None needed (lookup by PK only)
TTL: created_at + 5 minutes
```

### API Changes

**GET /api/v2/auth/oauth/urls Response** (updated):
```json
{
  "providers": {
    "google": {
      "authorize_url": "https://...?state=abc123...",
      "icon": "google"
    }
  },
  "state": "abc123..."
}
```

**POST /api/v2/auth/oauth/callback Request** (updated):
```json
{
  "code": "auth_code",
  "provider": "google",
  "redirect_uri": "https://...",
  "state": "abc123..."
}
```

### Validation Flow

```
1. Client calls GET /oauth/urls
2. Backend generates state, stores in DynamoDB, returns URLs with state
3. User completes OAuth on provider
4. Client calls POST /oauth/callback with code + state
5. Backend validates:
   a. State exists in DynamoDB
   b. State not expired (created_at < 5 min ago)
   c. State not already used
   d. state.provider matches request.provider
   e. state.redirect_uri matches request.redirect_uri
6. If valid: mark state as used, proceed with authentication
7. If invalid: return 400 "Invalid OAuth state" (generic message)
```
