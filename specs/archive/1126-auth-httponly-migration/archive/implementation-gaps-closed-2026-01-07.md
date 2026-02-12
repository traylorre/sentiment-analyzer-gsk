# Implementation Gaps: spec-v2.md vs Current Implementation

**Generated**: 2026-01-06
**Spec Version**: v3.0
**Status**: Audit findings requiring implementation work

---

## Critical Priority (Security/Breaking)

### 1. SameSite Cookie Attribute

| Aspect | Spec (authoritative) | Implementation | Location |
|--------|---------------------|----------------|----------|
| Value | `SameSite=None` | `samesite="strict"` | router_v2.py:404, :467 |
| CSRF Required | Yes (double-submit pattern) | Not implemented | N/A |

**Spec References**:
- Line 374: "SameSite CHANGED Strict → None + CSRF tokens"
- Line 900: "When using SameSite=None, CSRF protection via double-submit cookie pattern is mandatory"
- Line 6090-6091: "SameSite: None - v3.0: Required for cross-origin OAuth redirect flows"

**Implementation Required**:
1. Change `samesite="strict"` to `samesite="none"` in:
   - `src/lambdas/dashboard/router_v2.py:404` (magic link callback)
   - `src/lambdas/dashboard/router_v2.py:467` (OAuth callback)

2. Implement CSRF double-submit cookie pattern (spec lines 912-922):
   ```python
   CSRF_COOKIE_NAME = "csrf_token"

   def generate_csrf_token() -> str:
       return secrets.token_urlsafe(32)

   def validate_csrf_token(cookie_token: str | None, header_token: str | None) -> bool:
       if not cookie_token or not header_token:
           return False
       return secrets.compare_digest(cookie_token, header_token)
   ```

3. Add CSRF validation middleware for state-changing endpoints

---

### 2. CloudFront CORS Credentials

| Aspect | Spec (authoritative) | Implementation | Location |
|--------|---------------------|----------------|----------|
| allow_credentials | `true` | `false` | cloudfront/main.tf:151 |

**Spec Reference**:
- Line 6105: "CORS configuration required: SameSite=None only works with proper CORS setup (credentials: 'include')"

**Implementation Required**:
```hcl
# modules/cloudfront/main.tf:151
# Change from:
access_control_allow_credentials = false
# To:
access_control_allow_credentials = true
```

---

## High Priority (Schema/Data Model)

### 3. User Model Missing Fields

**Current User model** (`src/lambdas/shared/models/user.py`):

| Field | Type | Status |
|-------|------|--------|
| user_id | str | Implemented |
| email | EmailStr \| None | **RENAME** to `primary_email` |
| cognito_sub | str \| None | Not in spec (keep for compat?) |
| auth_type | Literal["anonymous", "email", "google", "github"] | **REPLACE** with `role` |
| created_at | datetime | Implemented |
| last_active_at | datetime | Not in spec (keep?) |
| session_expires_at | datetime | Not in spec (keep?) |
| timezone | str | Not in spec (keep?) |
| email_notifications_enabled | bool | Not in spec (keep?) |
| daily_email_count | int | Not in spec (keep?) |
| entity_type | str | Not in spec (keep for DynamoDB GSI) |
| revoked | bool | Not in spec (keep for session mgmt) |
| revoked_at | datetime \| None | Not in spec (keep for session mgmt) |
| revoked_reason | str \| None | Not in spec (keep for audit) |
| merged_to | str \| None | Implemented |
| merged_at | datetime \| None | Implemented |
| subscription_active | bool | Related to `role` derivation |
| subscription_expires_at | datetime \| None | Related to `role` derivation |
| is_operator | bool | Related to `role` derivation |

**Spec-required fields MISSING from implementation** (lines 4177-4196):

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `role` | `Literal["anonymous", "free", "paid", "operator"]` | `"anonymous"` | Authorization tier (replaces auth_type semantics) |
| `verification` | `Literal["none", "pending", "verified"]` | `"none"` | Email verification state |
| `pending_email` | `str \| None` | `None` | Email awaiting verification |
| `primary_email` | `str \| None` | `None` | Verified canonical email (rename from `email`) |
| `linked_providers` | `list[Literal["email", "google", "github"]]` | `[]` | List of linked auth providers |
| `provider_metadata` | `dict[str, ProviderMetadata]` | `{}` | Metadata per provider |
| `last_provider_used` | `Literal["email", "google", "github"] \| None` | `None` | For avatar selection |
| `role_assigned_at` | `datetime \| None` | `None` | Audit: when role changed |
| `role_assigned_by` | `str \| None` | `None` | Audit: "stripe_webhook" or "admin:{id}" |

**ProviderMetadata class MISSING** (spec lines 4168-4174):
```python
class ProviderMetadata(BaseModel):
    """Metadata for a linked auth provider."""
    sub: str | None = None           # Provider's subject claim (OAuth only)
    email: str | None = None         # Email from this provider
    avatar: str | None = None        # Avatar URL from provider
    linked_at: datetime              # When this provider was linked
    verified_at: datetime | None = None  # For email provider
```

---

### 3.1 Role-Verification Invariants (CRITICAL)

**There is NO `anonymous:verified` state.** Verification completion triggers role upgrade.

#### Valid State Matrix

| Role | verification=none | verification=pending | verification=verified |
|------|-------------------|---------------------|----------------------|
| `anonymous` | Valid | Valid | **INVALID** |
| `free` | **INVALID** | **INVALID** | Valid |
| `paid` | **INVALID** | **INVALID** | Valid |
| `operator` | **INVALID** | **INVALID** | Valid |

#### State Transitions (spec lines 4521-4532)

```
anonymous:none ──[claim email]──→ anonymous:pending ──[click link]──→ free:verified
                                                                   ↗
anonymous:none ──[Google OAuth]──→ free:verified
              ──[GitHub OAuth]──→ free:verified
```

**Key insight**: The act of verification IS the role upgrade. A user cannot be both anonymous and verified.

#### Implementation Constraint

Enforce in User model validator:
```python
from pydantic import model_validator

class User(BaseModel):
    role: Literal["anonymous", "free", "paid", "operator"] = "anonymous"
    verification: Literal["none", "pending", "verified"] = "none"

    @model_validator(mode="after")
    def validate_role_verification_invariant(self) -> "User":
        """Enforce role-verification invariants.

        - anonymous users can only have verification in ["none", "pending"]
        - non-anonymous users must have verification="verified"
        """
        if self.role == "anonymous" and self.verification == "verified":
            raise ValueError(
                "Invalid state: anonymous:verified is contradictory. "
                "Verification completion upgrades role to 'free'."
            )
        if self.role in ["free", "paid", "operator"] and self.verification != "verified":
            raise ValueError(
                f"Invalid state: {self.role}:{self.verification}. "
                f"Non-anonymous users must have verification='verified'."
            )
        return self
```

**Spec References**:
- Line 4523: `| anonymous | Magic link click | N/A | → free:email |`
- Line 4264: "Upgrade to free:verified"
- Line 5080-5081: "anonymous role cannot coexist with other roles"

---

## Medium Priority (Correctness)

### 4. Refresh Token Endpoint - Body vs Cookie

| Aspect | Spec (authoritative) | Implementation | Location |
|--------|---------------------|----------------|----------|
| Token source | Cookie (auto-sent) | Request body JSON | router_v2.py:~479-485 |

**Spec Reference** (lines 717-719):
```
POST /api/v2/auth/refresh
(NO BODY - cookie sent auto)
Cookie: refresh_token=xyz
```

**Current Implementation**:
```python
@auth_router.post("/refresh")
async def refresh_tokens(body: RefreshTokenRequest):
    result = auth_service.refresh_access_tokens(refresh_token=body.refresh_token)
```

**Implementation Required**:
- Extract refresh_token from `request.cookies` instead of body
- Remove `RefreshTokenRequest` body requirement

---

### 5. Cache-Control Headers on Auth Responses

| Aspect | Spec (authoritative) | Implementation | Location |
|--------|---------------------|----------------|----------|
| Cache-Control | `no-store, no-cache, must-revalidate` | Not set | router_v2.py auth endpoints |
| Pragma | `no-cache` | Not set | router_v2.py auth endpoints |
| Expires | `0` | Not set | router_v2.py auth endpoints |

**Spec Reference** (line 1091):
```python
response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
response.headers["Pragma"] = "no-cache"
response.headers["Expires"] = "0"
```

---

## Implementation Phases

Per spec-v2.md phase ordering:

| Phase | Items from this document | Breaking? |
|-------|-------------------------|-----------|
| Phase 1 (Backend Non-Breaking) | Cache-Control headers | No |
| Phase 2 (Frontend Breaking) | SameSite=None + CSRF, CloudFront CORS | Yes |
| Phase 2 (Frontend Breaking) | User model field additions | Yes (additive) |
| Phase 2 (Frontend Breaking) | Refresh endpoint cookie extraction | Yes |

---

## Recommended Implementation Order

1. **Add Cache-Control headers** (non-breaking, immediate)
2. **Add User model fields** (additive, database migration)
3. **Implement CSRF tokens** (prerequisite for SameSite change)
4. **Change SameSite + CloudFront CORS** (coordinated deployment)
5. **Refactor refresh endpoint** (frontend coordination required)

---

## Files Requiring Changes

| File | Changes |
|------|---------|
| `src/lambdas/dashboard/router_v2.py` | SameSite, Cache-Control, refresh endpoint |
| `src/lambdas/shared/models/user.py` | Add missing fields, ProviderMetadata |
| `src/lambdas/shared/middleware/csrf.py` | New file - CSRF implementation |
| `infrastructure/terraform/modules/cloudfront/main.tf` | CORS credentials |
| `tests/unit/` | Tests for all changes |

---

## Spec-v2.md Line References

| Topic | Lines |
|-------|-------|
| SameSite decision | 374, 427, 440, 6090-6091 |
| CSRF requirement | 900, 912-922, 6103 |
| CORS credentials | 6105 |
| User model fields | 4177-4196 |
| ProviderMetadata | 4168-4174 |
| Verification states | 4185 |
| Role-verification invariants | 4521-4532, 4264, 5080-5081 |
| State transitions | 4205-4233, 4521-4532 |
| Cache-Control | 1091-1093 |
| Refresh endpoint | 717-719 |
