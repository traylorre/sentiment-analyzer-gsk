# Feature Specification: Auth Architecture Rewrite (v2.8 - Deep Audit Remediation)

**Feature Branch**: `1126-auth-rewrite`
**Created**: 2026-01-03
**Updated**: 2026-01-03
**Status**: Draft v2.8 - Deep Audit Complete
**Priority**: P0 - Security + Architecture Foundation

---

## Changelog from v1

| Section | Change | Reason |
|---------|--------|--------|
| JWT Secret Management | **ADDED** | v1 had no key management spec |
| CORS Configuration | **ADDED** | v1 assumed same-origin |
| Magic Link | **UPDATED** | Document existing backend implementation |
| Cookie Settings | **FIXED** | Backend uses `Strict`, spec said `Lax` |
| Concurrent Refresh | **ADDED** | v1 had race condition |
| Role Hierarchy | **CLARIFIED** | v1 was ambiguous on AND vs OR |
| Mock Tokens | **ADDRESSED** | Backend has mock generation - must guard |
| Hardcoded Secret | **FLAGGED** | MAGIC_LINK_SECRET fallback is dangerous |
| Frontend Deletions | **EXPLICIT** | List exactly what to remove |
| Anonymous Mode | **DOCUMENTED** | Browser behavior in incognito |

### v2.1 - Security Audit Findings (2026-01-03)

| Section | Change | Reason |
|---------|--------|--------|
| JWT Claims | **ADDED** `aud`, `nbf` | Prevent token replay and pre-dated tokens |
| JWT Claims | **ADDED** validation table | Explicit checks for all claims |
| Role Decorator | **FIXED** error message | Removed role leakage in 403 response |
| Magic Link URL | **CHANGED** query → path | Prevent token leakage via Referer/logs |
| Infrastructure Layer | **ADDED** | Document CloudFront/API Gateway cookie handling |
| Back Button | **ADDED** | Cache-Control headers for protected content |
| Network Failure | **ADDED** | Timeout handling for refresh requests |
| Phase 0 | **ADDED** | Critical security fixes before any feature work |
| Signout | **CLARIFIED** | Server-side revocation required |

### v2.2 - Deep Audit Findings (2026-01-03)

| Section | Change | Reason |
|---------|--------|--------|
| Phase 0 | **EXPANDED** | Added C4-C6 (unprotected admin endpoints, XSS exposure) |
| JWT Validation | **ADDED** middleware requirements | aud/nbf must be validated in auth_middleware.py |
| Cookie Extraction | **ADDED** | Middleware must extract httpOnly cookies |
| RBAC | **ADDED** Phase 1.5 | Foundation for paid/operator roles |
| Magic Link | **SIMPLIFIED** | Remove HMAC, use random tokens + atomic DB |
| Integration Tests | **ADDED** | Atomic token consumption tests |
| 401 Interceptor | **CLARIFIED** | Frontend retry logic requirements |
| spec.md (v1) | **ARCHIVED** | spec-v2.md is now canonical |

### v2.3 - Principal Engineer Audit (2026-01-03)

| Section | Change | Reason |
|---------|--------|--------|
| Endpoint Table | **FIXED** | Removed `/<sig>` from magic link verify (HMAC removed) |
| CORS Config | **DECIDED** | Same-origin deployment selected, no CSRF tokens needed |
| JWT Generation | **ADDED** | New section with `create_access_token()` and `create_refresh_token()` |
| Atomic Refresh | **ADDED** | Full `refresh_tokens()` implementation with DynamoDB conditional update |
| Rate Limiting | **ADDED** | New section with endpoint-specific limits and implementation |
| Success Criteria | **EXPANDED** | Added aud/nbf validation, hashed tokens, atomic rotation |
| Phase 1 | **UPDATED** | Removed vestigial `get_magic_link_secret()` references |
| Out of Scope | **UPDATED** | Removed rate limiting (now in-scope) |
| Testing | **UPDATED** | Removed `get_magic_link_secret()` test requirement |

**Audit Findings Addressed:**
- 5 CRITICAL issues identified and mitigated
- 8 HIGH issues documented with implementation code
- 2 vestigial content items removed
- 5 blind spots filled (JWT generation, atomic refresh, rate limiting, CORS decision, hashed tokens)

### v2.4 - Deep Implementation Audit (2026-01-03)

| Section | Change | Reason |
|---------|--------|--------|
| Spec vs Implementation | **ADDED** drift warnings | 4 CRITICAL discrepancies found between spec and code |
| localStorage | **CRITICAL** | Spec says memory-only, impl uses zustand persist |
| HMAC Secret | **CRITICAL** | Spec says random tokens, impl still uses hardcoded HMAC |
| JWT Validation | **CRITICAL** | Spec requires aud/nbf, middleware doesn't validate |
| cookies.ts | **MUST DELETE** | Vestigial file sets non-httpOnly cookies from JS |
| X-User-ID Header | **MUST REMOVE** | Legacy fallback enables impersonation attacks |
| @require_role | **NOT IMPLEMENTED** | Decorator specified but not in codebase |
| Rate Limiting | **NOT IMPLEMENTED** | Spec has limits, no DynamoDB counters exist |
| Blind Spots | **ADDED** 7 sections | Cross-tab, anon mode, secret rotation, etc. |
| Header Transform | **ADDED** | Layer-by-layer auth header documentation |
| Role Future-Proofing | **ADDED** | Explicit gaps for paid/operator roles |
| Vestigial Content | **REMOVED** | HMAC migration guide, redundant comments |

**v2.4 Audit Summary:**
- 4 CRITICAL spec-vs-implementation discrepancies
- 5 HIGH priority implementation gaps
- 7 blind spots documented
- 5 vestigial sections cleaned up
- Future-proofing checklist for paid/operator roles

### v2.5 - Security Hardening (2026-01-03)

| Section | Change | Reason |
|---------|--------|--------|
| B2 Private Browsing | **ADDED** implementation requirement | Toast warning for blocked cookies not specified |
| D6 @require_role | **UPGRADED** to Phase 0 blocker | Cannot protect C4/C5 endpoints without it |
| C4 Admin Revocation | **ADDED** explicit fix requirement | `/admin/sessions/revoke` unprotected |
| C5 User Lookup | **ADDED** explicit fix requirement | `/users/lookup` allows user enumeration |
| C2 Mock Tokens | **ADDED** env guard requirement | Production can generate fake tokens |
| C3 Magic Link Race | **ADDED** atomic consumption requirement | Non-atomic DynamoDB access allows reuse |
| Vestigial | **KEPT** HMAC migration guide | Instructional (tells what to delete), not dead code |

**v2.5 Deep Audit Findings:**
- 5 CRITICAL vulnerabilities (D1-D5) confirmed with CVSS scores
- 5 HIGH vulnerabilities (C2-C5, D6) blocking production
- B2 implementation gap: missing private browsing toast warning
- D6 upgraded: blocks C4/C5 fixes (decorator required first)
- HMAC migration guide retained: instructional content

**Phase 0 Fix Order (Must Be Sequential):**
1. C1/D2: Delete HMAC, implement random tokens
2. C2: Guard mock tokens with `AWS_LAMBDA_FUNCTION_NAME` check
3. C3: Atomic DynamoDB conditional update for magic links
4. D6: Implement `@require_role` decorator (blocks C4/C5)
5. D1: Remove zustand `persist()` middleware
6. D4: Delete `cookies.ts` entirely
7. D5: Remove X-User-ID fallback
8. D3: Add `aud` + `nbf` JWT validation
9. C4: Add `@require_role("admin")` to `/admin/sessions/revoke`
10. C5: Add `@require_role("admin")` to `/users/lookup`

### v2.6 - Deep Audit (2026-01-03)

| Section | Change | Reason |
|---------|--------|--------|
| JWT Claims | **EXPANDED** with `scopes`, `tier`, `org_id` | Future-proof for paid/operator roles |
| Concurrent Sessions | **ADDED** max 5 devices policy | Missing session limit spec |
| Password Change | **ADDED** token invalidation requirement | All sessions must expire on password change |
| Error Codes | **ADDED** AUTH_001-AUTH_010 taxonomy | Standardized error responses missing |
| JWT_SECRET Rotation | **ADDED** operational runbook | No rotation procedure documented |
| CSRF | **CLARIFIED** SameSite=Strict requirement | cookies.ts uses Lax (conflict) |
| Cookie Path | **FIXED** from `/` to `/api/v2/auth` | Over-broad cookie scope |
| Logging | **ADDED** PII guidelines | What to log/not log undefined |

**v2.6 Deep Audit Findings:**
- Role extensibility gap: JWT claims not future-proof for paid/operator
- Missing concurrent session limit (allows unlimited devices)
- Missing password change invalidation (tokens persist after password reset)
- Missing error code taxonomy (inconsistent error responses)
- Missing JWT_SECRET rotation runbook (operational blind spot)
- SameSite conflict: spec says Strict, cookies.ts uses Lax
- Cookie path over-broad: `/` exposes tokens to all routes

**Spec Additions (v2.6):**
1. Expanded JWT claims structure with scopes/tier/org_id
2. New section: Concurrent Session Limits
3. New section: Password Change Behavior
4. New section: Error Code Taxonomy
5. New section: JWT_SECRET Rotation Runbook
6. New section: Logging PII Guidelines

### v2.7 - Audit Fixes (2026-01-03)

| Section | Change | Reason |
|---------|--------|--------|
| Session Limits | **CRITICAL FIX** enforce at `create_access_token()` | Limits documented but not enforced (A1) |
| Password Change | **CRITICAL FIX** add `revocation_id` to JWT | Access tokens live 15min post-password-change (A2) |
| JWT Validation | **CRITICAL FIX** global aud/iss in decode | Per-endpoint validation allows bypass (A3) |
| X-User-ID | **REMOVED** all vestigial references | Lines 200, 827, 1984 still referenced deleted header (A4) |
| Magic Link | **CRITICAL FIX** reject `?token=` query params | Token leakage via logs/referer (A5) |
| Anonymous Sessions | **ADDED** limit to policy table | DOS via unlimited anon sessions (A6) |
| JWT Claims | **ADDED** `ver` claim | Future schema changes break old clients (A7) |
| OAuth Callback | **ADDED** state validation | CSRF attack vector (A8) |
| Revocation GC | **ADDED** TTL strategy | Blocklist grows unbounded (A9) |
| Role Naming | **CLARIFIED** `authenticated` = `free` tier | Confusion between role and tier (A10) |
| Rate Limiting | **EXPANDED** missing endpoints | `/signout`, `/session`, `/link-accounts` unprotected (A11) |
| Error Codes | **FIXED** leak prevention | `AUTH_010` distinguishes expired vs used (A12) |
| Cookie Path | **TIGHTENED** to `/api/v2/auth/refresh` | `/api/v2/auth` too broad (A13) |
| JWT Rotation | **CLARIFIED** validation order | Which key validates first undefined (A14) |

**v2.7 Audit Findings (14 issues):**

| ID | Severity | Issue | Risk |
|----|----------|-------|------|
| A1 | CRITICAL | Session limits not enforced at token creation | Unlimited sessions, attacker persistence |
| A2 | CRITICAL | Password change doesn't invalidate access tokens | Stolen token works 15min post-change |
| A3 | CRITICAL | aud/iss validated per-endpoint, not globally | Tokens from other services accepted |
| A4 | CRITICAL | X-User-ID header vestigial references | Confusion about removal status |
| A5 | CRITICAL | Magic link accepts `?token=` query params | Token leakage via Referer/logs |
| A6 | HIGH | Anonymous sessions not in limit table | DOS via 1000 anon sessions |
| A7 | HIGH | JWT claims not versioned | Schema changes break old clients |
| A8 | HIGH | OAuth callback lacks state validation | CSRF attack vector |
| A9 | HIGH | Token revocation list grows unbounded | DynamoDB cost scales with storage |
| A10 | MEDIUM | `authenticated` vs `free` naming confusion | Code expects different values |
| A11 | MEDIUM | Rate limits missing for 3 endpoints | DOS vectors |
| A12 | MEDIUM | Error code leaks state information | User enumeration via error messages |
| A13 | MEDIUM | Cookie path too broad | Unrelated auth endpoints read refresh token |
| A14 | MEDIUM | JWT rotation key order undefined | Tokens rejected prematurely |

**Spec Additions (v2.7):**
1. Session enforcement code in `create_access_token()`
2. `revocation_id` JWT claim with client-side check
3. Global JWT decode with aud/iss
4. Magic link endpoint rejects query params
5. Anonymous row in session limit table
6. `ver: 1` in JWT claims
7. OAuth state validation section
8. Token revocation GC strategy
9. Rate limits for `/signout`, `/session`, `/link-accounts`
10. Error response security guidelines

**Blind Spots Documented (v2.7, updated v2.8):**
- Device fingerprinting/binding not addressed
- Audit log format not specified
- Account merge race condition not specified
- CloudFront uses deprecated `forwarded_values` API
- ~~Cross-tab logout accepted as limitation~~ → v2.8: Implemented via BroadcastChannel

### v2.8 - Deep Audit Remediation (2026-01-03)

| Section | Change | Reason |
|---------|--------|--------|
| Cookie Path | **FIXED** `/api/v2/auth` → `/api/v2/auth/refresh` | Industry best practice: narrow scope |
| Anonymous Tier | **FIXED** `tier: null` (not `"free"`) | Anonymous has no billing relationship |
| Cross-Tab Logout | **IMPLEMENTED** BroadcastChannel | User requested explicit sync |
| Role vs Tier | **CLARIFIED** with concrete examples | Eliminate code confusion |
| Mid-Session Upgrade | **ADDED** tier upgrade flow | Future-proof for paid/operator |
| Safari ITP | **ADDED** compatibility section | Blind spot identified in audit |
| Missing Functions | **ADDED** 6 helper implementations | G1-G6 audit findings |
| DynamoDB Schemas | **ADDED** complete schemas | RateLimits, OAuthState, Sessions |
| User Model | **ADDED** `revocation_id` field | Required for A2 password invalidation |
| Session Limits | **FIXED** use role for anonymous | Consistent with role/tier separation |

**v2.8 Audit Findings Resolved:**

| ID | Category | Resolution |
|----|----------|------------|
| C1.1 | Session limits | `create_session_with_limit_enforcement()` fully implemented |
| C1.2 | Password change | `increment_revocation_id()` implementation added |
| C1.7 | OAuth state | `store_oauth_state()` / `consume_oauth_state()` implementations added |
| G1 | Token hashing | `store_refresh_token()` complete implementation |
| G2 | Rate limits | DynamoDB schema specified |
| G3 | Sessions | DynamoDB schema complete with all fields |
| G4 | OAuth state | DynamoDB schema and functions specified |
| G5 | JWT helpers | `get_user_revocation_id()`, `session_exists()` implemented |
| G6 | Cookie detection | Integration point clarified in AuthProvider |
| V2 | Cookie path | Contradiction resolved: `/api/v2/auth/refresh` |
| V3 | Anonymous tier | Contradiction resolved: `tier: null` |

**New Sections Added (v2.8):**
1. Cross-Tab Auth Synchronization (BroadcastChannel)
2. Safari ITP Compatibility
3. Mid-Session Tier Upgrade Flow
4. Complete DynamoDB Schema Reference
5. Role vs Tier Decision Matrix
6. Missing Helper Function Implementations

---

## Problem Statement

Current auth implementation has fundamental flaws:

1. **Tokens in localStorage** - XSS can read them
2. **Tokens in non-httpOnly cookies** - XSS can read them
3. **Zustand persist for tokens** - Writes to localStorage
4. **Refresh token in request body** - Should be httpOnly cookie only
5. **No role-based decorators** - Endpoints check auth ad-hoc
6. **Hardcoded fallback secret** - MAGIC_LINK_SECRET has dangerous default
7. **Mock token generation in production path** - Not guarded

### What Backend Already Does Right

The backend has sophisticated auth that the spec didn't document:

- **Magic Link**: Random tokens (256-bit), 1-hour expiry, atomic one-time use
- **OAuth**: Google + GitHub via Cognito with proper code exchange
- **Session Revocation**: Admin andon cord with audit trails
- **Account Merging**: Tombstone pattern, idempotent, concurrent-safe
- **Email Uniqueness**: GSI with race condition protection
- **Sanitized Logging**: CRLF injection prevention

---

## ⚠️ CRITICAL: Spec vs Implementation Drift (v2.5)

**STATUS: Implementation does NOT match this specification.**

Before implementing any new features, these discrepancies MUST be resolved:

### CRITICAL Discrepancies (Block All Work) - CVSS 7.4+

| ID | Spec Says | Implementation Does | File:Line | Fix Required | CVSS |
|----|-----------|---------------------|-----------|--------------|------|
| D1 | Access token in memory only | zustand persist → localStorage | `auth-store.ts:279-306` | Remove persist middleware | 8.6 |
| D2 | Random tokens for magic link | HMAC with hardcoded secret | `auth.py:1101-1114` | Delete HMAC, use `secrets.token_urlsafe(32)` | 9.1 |
| D3 | Validate `aud`, `nbf` claims | Only validates `exp`, `iss` | `auth_middleware.py:112-169` | Add audience/nbf to decode options | 7.8 |
| D4 | No JS-accessible cookies | Sets cookies via `document.cookie` | `cookies.ts:1-40` | DELETE entire file | 8.6 |
| D5 | Bearer tokens only | Falls back to X-User-ID header | `auth_middleware.py:200-207` | Remove X-User-ID fallback | 7.4 |

### HIGH Discrepancies (Block Feature Work) - CVSS 5.3-7.8

| ID | Spec Says | Implementation Does | File:Line | Fix Required | CVSS |
|----|-----------|---------------------|-----------|--------------|------|
| C2 | Mock tokens only in dev | No environment guard | `auth.py:1510-1529` | Add `AWS_LAMBDA_FUNCTION_NAME` check | 7.8 |
| C3 | Atomic magic link consumption | Non-atomic get/check/update | `auth.py` (magic link) | Use DynamoDB conditional update | 6.5 |
| C4 | Admin endpoints protected | `/admin/sessions/revoke` unprotected | `router_v2.py:517` | Add `@require_role("admin")` | 8.2 |
| C5 | Admin endpoints protected | `/users/lookup` allows enumeration | `router_v2.py:673` | Add `@require_role("admin")` | 5.3 |
| D6 | `@require_role` decorator | No decorator exists | (missing) | Implement per lines 712-789 | 7.2 |
| D7 | Rate limiting per endpoint | No rate limiting | (missing) | Implement per lines 1943-2015 | 5.3 |
| D8 | Refresh token rotation | Cognito doesn't rotate | `cognito.py:253` | Document limitation OR implement custom | 4.0 |
| D9 | Signout revokes refresh token | Only revokes sessions | `auth.py:835-893` | Add REFRESH# revocation | 4.0 |

### Resolution Protocol (v2.5 - Sequential Order)

**Phase 0 (Block Production)** - Must complete in order:
1. D2/C1: Delete HMAC, implement random tokens
2. C2: Guard mock tokens with env check
3. C3: Atomic DynamoDB conditional update for magic links
4. D6: Implement `@require_role` decorator (blocks C4/C5)
5. D1: Remove zustand `persist()` middleware
6. D4: Delete `cookies.ts` entirely
7. D5: Remove X-User-ID fallback
8. D3: Add `aud` + `nbf` JWT validation
9. C4: Add `@require_role("admin")` to `/admin/sessions/revoke`
10. C5: Add `@require_role("admin")` to `/users/lookup`

**Phase 1 (Post-Production)**:
- D7: Rate limiting implementation
- D8: Document Cognito rotation limitation
- D9: Add refresh token revocation to signout

**No new features until Phase 0 (D1-D5, C2-C5, D6) resolved.**

---

## Target Architecture

```
+------------------------------------------------------------------+
|                         AUTH FLOW                                 |
+------------------------------------------------------------------+

LOGIN (any method: anonymous, magic link, OAuth)
====================================================================
Client                               Server
  |                                    |
  |  POST /api/v2/auth/{method}        |
  |  { credentials }  --------------->  |
  |                                    |  Validate credentials
  |                                    |  Generate JWT:
  |                                    |    sub: user_id
  |                                    |    email: optional
  |                                    |    roles: ["authenticated"]
  |                                    |    iat: now
  |                                    |    exp: now + 15min
  |                                    |  Generate refresh token
  |                                    |
  |  <---------------------------------|
  |  Body: { access_token, user }      |
  |  Set-Cookie: refresh_token=xyz;    |
  |    HttpOnly; Secure; SameSite=Strict; Path=/api/v2/auth
  |                                    |
  |  Store access_token IN MEMORY      |
  |  (JS variable, NOT localStorage)   |
  |                                    |

API REQUESTS
====================================================================
Client                               Server
  |                                    |
  |  GET /api/v2/settings              |
  |  Authorization: Bearer {token} --> |
  |                                    |  @require_role("authenticated")
  |                                    |  1. Extract Bearer token
  |                                    |  2. Validate JWT sig + exp
  |                                    |  3. Check roles in claims
  |                                    |  4. 200 or 401/403
  |  <---------------------------------|
  |  Response or error                 |

TOKEN REFRESH
====================================================================
Client                               Server
  |                                    |
  |  POST /api/v2/auth/refresh         |
  |  (NO BODY - cookie sent auto)      |
  |  Cookie: refresh_token=xyz ------> |  (browser sends automatically)
  |                                    |  Validate refresh token
  |                                    |  Issue new access_token
  |                                    |  Rotate refresh token
  |  <---------------------------------|
  |  Body: { access_token, user }      |
  |  Set-Cookie: refresh_token=new     |

PAGE LOAD (session restore)
====================================================================
Client                               Server
  |                                    |
  |  POST /api/v2/auth/refresh ------> |  (try to restore session)
  |  Cookie sent automatically         |
  |                                    |
  |  <---------------------------------|
  |  200 + new token = logged in       |
  |  401 = not logged in (OK for new)  |
```

---

## JWT Secret Management (NEW - CRITICAL)

### Key Storage

```python
# src/lambdas/shared/config/secrets.py
import os
import boto3
from functools import lru_cache

class SecretNotConfiguredError(Exception):
    """Raised when required secret is not available."""
    pass

@lru_cache(maxsize=1)
def get_jwt_secret() -> str:
    """
    Get JWT signing secret. Fails hard if not configured.

    Priority:
    1. AWS Secrets Manager (production)
    2. Environment variable (local dev only)

    NEVER falls back to a hardcoded default.
    """
    # Production: use Secrets Manager
    secret_arn = os.environ.get("JWT_SECRET_ARN")
    if secret_arn:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_arn)
        return response["SecretString"]

    # Local dev: use environment variable
    secret = os.environ.get("JWT_SECRET")
    if secret:
        if len(secret) < 32:
            raise SecretNotConfiguredError(
                "JWT_SECRET must be at least 32 characters"
            )
        return secret

    raise SecretNotConfiguredError(
        "JWT_SECRET_ARN (production) or JWT_SECRET (local) must be set"
    )

# NOTE: get_magic_link_secret() REMOVED
# Magic links now use cryptographically random tokens (secrets.token_urlsafe)
# No HMAC signing means no secret to manage
# See "Magic Link (Simplified Architecture)" section
```

### JWT Configuration

```python
# src/lambdas/shared/config/jwt_config.py
from dataclasses import dataclass

@dataclass(frozen=True)
class JWTConfig:
    """JWT configuration. Immutable after creation."""
    algorithm: str = "HS256"  # Symmetric for single-service
    issuer: str = "sentiment-analyzer"
    access_token_expiry_seconds: int = 900  # 15 minutes
    refresh_token_expiry_seconds: int = 604800  # 7 days
    clock_skew_seconds: int = 60  # Leeway for clock drift

JWT_CONFIG = JWTConfig()
```

### Terraform for Secrets Manager

```hcl
# infrastructure/terraform/modules/secrets/main.tf
resource "aws_secretsmanager_secret" "jwt_secret" {
  name        = "${var.project}-jwt-secret-${var.environment}"
  description = "JWT signing secret for ${var.project}"

  tags = {
    Purpose = "auth"
    Rotate  = "quarterly"
  }
}

# NOTE: magic_link_secret REMOVED
# Magic links now use cryptographically random tokens (secrets.token_urlsafe)
# No HMAC signing means no secret to manage

# Lambda IAM policy
resource "aws_iam_policy" "lambda_secrets_read" {
  name = "${var.project}-lambda-secrets-read"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.jwt_secret.arn,
      ]
    }]
  })
}
```

---

## CORS Configuration (NEW - CRITICAL)

### Same-Origin Deployment (Recommended)

```
Frontend: https://app.example.com
API:      https://app.example.com/api/v2/*

Cookies work automatically (same origin).
No special CORS headers needed.
```

### Cross-Origin Deployment

If frontend and API are on different domains:

```python
# src/lambdas/dashboard/cors.py
from fastapi.middleware.cors import CORSMiddleware

CORS_CONFIG = {
    "allow_origins": [
        os.environ.get("FRONTEND_ORIGIN", "https://app.example.com"),
    ],
    "allow_credentials": True,  # REQUIRED for cookies
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Authorization", "Content-Type"],
}

# In router setup:
app.add_middleware(CORSMiddleware, **CORS_CONFIG)
```

### Cookie Domain Settings

```python
# For cross-origin cookies to work:
COOKIE_SETTINGS = {
    "httponly": True,
    "secure": True,
    "samesite": "none",  # Required for cross-origin
    "domain": ".example.com",  # Shared parent domain
    "path": "/api/v2/auth",
}
```

**DECISION (v2.3)**: Same-origin deployment selected.
- Frontend: `https://<app>.amplifyapp.com`
- API: `https://<app>.amplifyapp.com/api/v2/*` (via CloudFront)
- Cookie settings: `SameSite=Strict`, no domain attribute
- No CSRF tokens needed (SameSite=Strict blocks cross-origin POST)

If cross-origin deployment is required later, update to `SameSite=None; Secure` and add CSRF protection.

---

## Infrastructure Layer (API Gateway / CloudFront) (NEW - CRITICAL)

Auth tokens pass through multiple layers. Each must be configured correctly:

### Request Flow (Browser → Lambda)

```
Browser → CloudFront → API Gateway → Lambda
         ↓             ↓              ↓
         Cookies       Headers        Validation
         forwarded     passed         performed
```

### CloudFront Configuration

```hcl
# infrastructure/terraform/modules/cloudfront/main.tf
resource "aws_cloudfront_distribution" "api" {
  # ...

  default_cache_behavior {
    # Forward cookies to origin (required for httpOnly refresh token)
    forwarded_values {
      cookies {
        forward = "whitelist"
        whitelisted_names = ["refresh_token"]
      }
    }

    # Cache policy: Do NOT cache auth responses
    cache_policy_id = aws_cloudfront_cache_policy.no_cache_auth.id
  }
}

resource "aws_cloudfront_cache_policy" "no_cache_auth" {
  name = "no-cache-auth"

  default_ttl = 0
  max_ttl     = 0
  min_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "whitelist"
      cookies { items = ["refresh_token"] }
    }
    headers_config {
      header_behavior = "whitelist"
      headers { items = ["Authorization", "Origin"] }
    }
  }
}
```

### API Gateway Configuration

```hcl
# infrastructure/terraform/modules/api_gateway/main.tf
resource "aws_apigatewayv2_api" "main" {
  # ...

  cors_configuration {
    allow_origins     = var.allowed_origins  # ["https://app.example.com"]
    allow_methods     = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers     = ["Authorization", "Content-Type"]
    allow_credentials = true  # Required for cookies
    max_age           = 86400  # Preflight cache: 24 hours
  }
}
```

### Response Headers (Lambda → Browser)

Lambda MUST set these headers on auth responses:

```python
# All auth endpoints
response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
response.headers["Pragma"] = "no-cache"
response.headers["Expires"] = "0"

# Cross-origin only (if applicable)
response.headers["Access-Control-Allow-Origin"] = allowed_origin
response.headers["Access-Control-Allow-Credentials"] = "true"
```

### Set-Cookie Flow

```
Lambda sets:     Set-Cookie: refresh_token=xxx; HttpOnly; Secure; SameSite=Strict
API Gateway:     Passes through (no transformation)
CloudFront:      Passes through (no transformation)
Browser:         Stores cookie, sends on subsequent requests to /api/v2/auth/*
```

**CRITICAL**: If any layer strips or modifies Set-Cookie, auth will silently fail.

---

## Role System

### Role vs Tier Clarification (A10 FIX)

**IMPORTANT**: Roles and Tiers are DIFFERENT concepts:

| Concept | Purpose | Values | JWT Field |
|---------|---------|--------|-----------|
| **Role** | Authorization (what can you do?) | `anonymous`, `authenticated`, `paid`, `operator` | `roles[]` |
| **Tier** | Billing (what limits apply?) | `free`, `paid`, `operator` | `tier` |

**Mapping**:
| Role | Default Tier | Notes |
|------|--------------|-------|
| `anonymous` | N/A | No tier (ephemeral session) |
| `authenticated` | `free` | Email verified, no subscription |
| `paid` | `paid` | Has active subscription |
| `operator` | `operator` | Internal team member |

**A10 FIX**: The `authenticated` ROLE maps to `free` TIER by default.
Code MUST NOT confuse `authenticated` (role) with `free` (tier).

```python
# CORRECT: Role and tier are separate
roles = ["authenticated"]  # Role: logged in
tier = "free"              # Tier: no subscription

# WRONG: Don't use role names as tier values
tier = "authenticated"     # ERROR: authenticated is a role, not a tier
```

### Role Definition

```python
# src/lambdas/shared/models/roles.py
from enum import Enum

class Role(str, Enum):
    """
    User roles. Users can have MULTIPLE roles (additive).

    Hierarchy (implicit, not enforced):
      operator > paid > authenticated > anonymous

    Roles are NOT mutually exclusive:
      - An operator also has authenticated
      - A paid user also has authenticated
      - Anonymous users ONLY have anonymous

    NOTE (A10): Roles are NOT tiers. authenticated != free.
    - authenticated is a ROLE (can do X)
    - free is a TIER (limited to Y)
    """
    ANONYMOUS = "anonymous"           # Temporary session, no email
    AUTHENTICATED = "authenticated"   # Logged in with verified email
    PAID = "paid"                     # Active subscription (future)
    OPERATOR = "operator"             # Admin access (future)

def get_roles_for_user(user: "User") -> list[str]:
    """
    Determine roles based on user state.

    Returns list of ALL applicable roles (additive).
    """
    if user.auth_type == "anonymous":
        return [Role.ANONYMOUS.value]

    roles = [Role.AUTHENTICATED.value]

    if user.subscription_active:  # Future field
        roles.append(Role.PAID.value)

    if user.is_operator:  # Future field
        roles.append(Role.OPERATOR.value)

    return roles
```

### JWT Claims Structure

```json
{
  "sub": "user-123",
  "email": "user@example.com",
  "roles": ["authenticated"],
  "scopes": ["read:metrics", "write:settings"],
  "tier": "free",
  "org_id": null,
  "ver": 1,
  "rev": 0,
  "sid": "session-456",
  "iat": 1704307200,
  "exp": 1704308100,
  "nbf": 1704307200,
  "iss": "sentiment-analyzer",
  "aud": "sentiment-analyzer-api"
}
```

**Required Claims** (all MUST be validated):
| Claim | Purpose | Validation |
|-------|---------|------------|
| `sub` | User ID | Must exist, non-empty |
| `iat` | Issued At | Must be in past (with 60s clock skew tolerance) |
| `exp` | Expiry | Must be in future |
| `nbf` | Not Before | Must be in past (prevents pre-dated tokens) |
| `iss` | Issuer | Must equal `"sentiment-analyzer"` |
| `aud` | Audience | Must equal `"sentiment-analyzer-api"` (prevents token replay to other services) |
| `ver` | Schema version | Must equal `1` (future schema changes) |
| `rev` | Revocation counter | Must match user's current `revocation_id` in DB (A2 fix) |
| `sid` | Session ID | Must exist in active sessions table (A1 fix) |

**Future-Proof Claims (v2.6):**
| Claim | Purpose | Values | Required |
|-------|---------|--------|----------|
| `scopes` | Fine-grained permissions | `["read:metrics", "write:settings", "admin:users"]` | Optional (empty array default) |
| `tier` | Billing tier | `"free"`, `"paid"`, `"operator"` | Required (default `"free"`) |
| `org_id` | Multi-tenancy org | UUID or `null` for personal | Optional (null default) |

**Role → Scope Mapping:**
| Role | Default Scopes |
|------|----------------|
| `anonymous` | `["read:public"]` |
| `authenticated` | `["read:metrics", "write:settings"]` |
| `paid` | `["read:metrics", "write:settings", "read:analytics", "export:data"]` |
| `operator` | `["admin:users", "admin:sessions", "admin:config"]` |
| `admin` | `["*"]` (all scopes) |

**Tier Hierarchy:**
```
free < paid < operator
```
- `free`: Default for all authenticated users
- `paid`: Users with active subscription (future: Stripe integration)
- `operator`: Internal team members (future: SSO via Okta/Azure AD)

**Token Size Constraint**: Max 10 roles, 20 scopes, 32-char names. Total JWT < 4KB.

**Note (v2.8)**: Anonymous users have `email: null`, `roles: ["anonymous"]`, `tier: null`, `scopes: ["read:public"]`.
Anonymous has no billing tier (no payment relationship). Use role for session limit lookup.

### JWT Generation (REQUIRED - Previously Missing)

**The spec showed JWT claims and validation but NOT generation. Here is the required implementation:**

```python
# src/lambdas/shared/auth/jwt.py (NEW FILE)
import jwt
import secrets
from datetime import datetime, timedelta, UTC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.lambdas.shared.models.user import User

from src.lambdas.shared.config.secrets import get_jwt_secret
from src.lambdas.shared.config.jwt_config import JWT_CONFIG
from src.lambdas.shared.models.role import get_roles_for_user


async def create_access_token(user: "User", device_info: dict | None = None) -> str:
    """
    Generate JWT access token with all required claims.

    ALL claims are mandatory - missing any will cause validation failures.

    CRITICAL (A1): This function MUST enforce session limits BEFORE issuing tokens.
    Session creation happens here, not after login completes.
    """
    now = datetime.now(UTC)
    secret = get_jwt_secret()  # Fails if not configured

    # A1 FIX: Enforce session limits at token creation time
    # This prevents unlimited session proliferation
    tier = getattr(user, 'tier', 'free')
    session_id = await create_session_with_limit_enforcement(
        user_id=user.user_id,
        tier=tier,
        device_info=device_info or {},
    )

    # A2 FIX: Get user's current revocation counter
    # Password changes increment this, invalidating all prior tokens
    revocation_id = await get_user_revocation_id(user.user_id)

    claims = {
        # Identity
        "sub": user.user_id,
        "email": user.email,  # null for anonymous
        "roles": get_roles_for_user(user),

        # A7 FIX: Schema version for backward compatibility
        "ver": 1,

        # A2 FIX: Revocation counter (invalidates tokens on password change)
        "rev": revocation_id,

        # A1 FIX: Session ID (must be in active sessions table)
        "sid": session_id,

        # Temporal (all required)
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=JWT_CONFIG.access_token_expiry_seconds)).timestamp()),
        "nbf": int(now.timestamp()),  # Not-before = now (prevents pre-dated tokens)

        # Verification
        "iss": JWT_CONFIG.issuer,
        "aud": "sentiment-analyzer-api",  # Prevents cross-service replay
    }

    return jwt.encode(claims, secret, algorithm=JWT_CONFIG.algorithm)


def create_refresh_token() -> tuple[str, str]:
    """
    Generate refresh token pair: (plaintext for cookie, hash for storage).

    Returns:
        (token, token_hash) - NEVER store plaintext in database
    """
    token = secrets.token_urlsafe(32)  # 256-bit entropy
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash
```

**Usage in auth endpoints:**
```python
# src/lambdas/dashboard/auth.py - any login endpoint

async def complete_login(user: User, response: Response):
    """Issue tokens after successful authentication."""
    # 1. Generate access token (JWT with all claims)
    access_token = create_access_token(user)

    # 2. Generate refresh token (random, hashed for storage)
    refresh_token, refresh_hash = create_refresh_token()

    # 3. Store refresh token hash in DynamoDB
    now = datetime.now(UTC)
    expires = now + timedelta(seconds=JWT_CONFIG.refresh_token_expiry_seconds)
    await store_refresh_token(
        user_id=user.user_id,
        token_hash=refresh_hash,
        expires_at=expires,
    )

    # 4. Set httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        **REFRESH_COOKIE_SETTINGS,
    )

    return {"access_token": access_token, "user": user.to_dict()}
```

### JWT Validation in auth_middleware.py (REQUIRED FIX)

**Current State** (auth_middleware.py:112-170): Only validates `sub`, `exp`, `iat`, `iss`. Missing `aud` and `nbf`.

**CRITICAL (A3)**: Validation MUST happen in the GLOBAL decode step, NOT per-endpoint in decorators.
If any endpoint forgets to pass `audience`, tokens from other services are accepted.

```python
# src/lambdas/shared/middleware/auth_middleware.py - REQUIRED UPDATE

# BEFORE (VULNERABLE)
payload = jwt.decode(
    token,
    config.secret,
    algorithms=[config.algorithm],
    issuer=config.issuer,
    options={"require": ["sub", "exp", "iat"]},
)

# AFTER (SECURE - v2.7 with A1/A2/A3/A7 fixes)
async def validate_jwt_global(token: str) -> dict | None:
    """
    GLOBAL JWT validation. ALL tokens MUST pass through this function.

    A3 FIX: aud/iss validated HERE, not in per-endpoint decorators.
    """
    try:
        # Cryptographic validation (aud/iss/nbf ALWAYS checked)
        payload = jwt.decode(
            token,
            config.secret,
            algorithms=[config.algorithm],
            issuer="sentiment-analyzer",           # A3: Global, not per-endpoint
            audience="sentiment-analyzer-api",     # A3: Global, not per-endpoint
            options={
                "require": ["sub", "exp", "iat", "nbf", "aud", "ver", "rev", "sid"],
                "verify_nbf": True,
                "verify_aud": True,
            },
        )

        # A7 FIX: Schema version check
        if payload.get("ver") != 1:
            logger.warning("jwt_version_mismatch", ver=payload.get("ver"))
            return None

        # A2 FIX: Revocation counter check (password change invalidates tokens)
        user_rev = await get_user_revocation_id(payload["sub"])
        if payload.get("rev", 0) != user_rev:
            logger.warning("jwt_revoked", user_id=payload["sub"], token_rev=payload.get("rev"), user_rev=user_rev)
            return None

        # A1 FIX: Session ID check (session must still be active)
        if not await session_exists(payload["sub"], payload.get("sid")):
            logger.warning("jwt_session_invalid", user_id=payload["sub"], sid=payload.get("sid"))
            return None

        return payload

    except jwt.ExpiredSignatureError:
        return None  # AUTH_003: Normal expiry, trigger refresh
    except jwt.InvalidAudienceError:
        logger.error("jwt_audience_mismatch")  # A3: Critical - potential cross-service attack
        return None
    except jwt.InvalidIssuerError:
        logger.error("jwt_issuer_mismatch")
        return None
    except jwt.DecodeError:
        return None  # AUTH_002: Malformed token
```

**Why this matters:**
- Without `aud`: Token for service A could be replayed to service B
- Without `nbf`: Attacker could pre-generate tokens for future use
- Without `rev`: Password change doesn't invalidate existing tokens (A2)
- Without `sid`: Session eviction doesn't invalidate tokens (A1)
- Without `ver`: Schema changes break old clients (A7)

### Cookie Extraction in auth_middleware.py (REQUIRED FIX)

**Current State** (auth_middleware.py:280-305): Only extracts from `Authorization` header. No cookie support.

```python
# src/lambdas/shared/middleware/auth_middleware.py - ADD

def extract_refresh_token_from_cookie(request: Request) -> str | None:
    """
    Extract refresh token from httpOnly cookie.

    Used by /api/v2/auth/refresh endpoint only.
    Regular API requests use Authorization header.
    """
    cookie_header = request.headers.get("Cookie", "")
    for cookie in cookie_header.split(";"):
        cookie = cookie.strip()
        if cookie.startswith("refresh_token="):
            return cookie[len("refresh_token="):]
    return None


def extract_auth_context(request: Request) -> AuthContext:
    """
    Extract authentication from request.

    Priority:
    1. Authorization: Bearer <jwt> header (API requests)
    2. refresh_token cookie (refresh endpoint only)

    NOTE: X-User-ID header support REMOVED in v2.4 (security risk - see D5)
    """
    # Try Bearer token first
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        claims = validate_jwt(token)
        if claims:
            return AuthContext(
                auth_type=AuthType.AUTHENTICATED,
                user_id=claims.sub,
                email=claims.email,
                roles=claims.roles,
            )

    # Try cookie for refresh endpoint
    if request.url.path == "/api/v2/auth/refresh":
        refresh_token = extract_refresh_token_from_cookie(request)
        if refresh_token:
            return AuthContext(
                auth_type=AuthType.REFRESH,
                refresh_token=refresh_token,
            )

    # Fallback: anonymous
    return AuthContext(auth_type=AuthType.ANONYMOUS, user_id=None)
```

### Role Decorator (Clarified)

```python
# src/lambdas/shared/middleware/require_role.py
from functools import wraps
from typing import Callable
from fastapi import HTTPException, Request
from .jwt import validate_jwt, JWTError

def require_role(*required_roles: str, match_all: bool = True):
    """
    Decorator to enforce role-based access control.

    Args:
        required_roles: Roles to check
        match_all: If True, user must have ALL roles (AND).
                   If False, user must have ANY role (OR).

    Usage:
        @require_role("authenticated")
        async def get_settings(): ...

        @require_role("authenticated", "paid", match_all=True)
        async def premium_feature(): ...  # Must have BOTH

        @require_role("operator", "paid", match_all=False)
        async def admin_or_paid(): ...  # Must have EITHER

    Returns:
        401 if no valid token
        403 if token valid but roles insufficient
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Extract token
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Missing or invalid Authorization header"
                )

            token = auth_header[7:]

            # Validate JWT
            try:
                claims = validate_jwt(token)
            except JWTError as e:
                raise HTTPException(status_code=401, detail=str(e))

            # Check roles
            user_roles = set(claims.get("roles", []))
            required = set(required_roles)

            if match_all:
                # AND: user must have all required roles
                has_access = required.issubset(user_roles)
            else:
                # OR: user must have at least one required role
                has_access = bool(required.intersection(user_roles))

            if not has_access:
                # SECURITY: Do not leak role requirements in error message
                raise HTTPException(
                    status_code=403,
                    detail="Access denied"
                )

            # Inject user context
            request.state.user_id = claims["sub"]
            request.state.email = claims.get("email")
            request.state.roles = user_roles

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
```

---

## Magic Link (Simplified Architecture)

### Design Decision: Random Token vs HMAC

**Previous approach**: HMAC-signed tokens required a `MAGIC_LINK_SECRET`.
**New approach**: Cryptographically random tokens with atomic DB verification.

| Approach | DoS Protection | Auth Security | Complexity |
|----------|---------------|---------------|------------|
| HMAC + DB | ✅ Reject before DB | Same | High (secret mgmt) |
| Random + DB + Rate Limit | ✅ Rate limit | Same | **Low** |

**Why remove HMAC?**
1. You MUST hit DynamoDB anyway for atomic consumption (mark as used)
2. DynamoDB is the source of truth - if token isn't there, it fails
3. Rate limiting on the endpoint provides equivalent DoS protection
4. One less secret to manage, rotate, and potentially leak

### Simplified Flow

```
1. User enters email in frontend form
2. POST /api/v2/auth/magic-link { email, anonymous_user_id? }
3. Backend:
   a. Validate email format
   b. Rate limit by email (5 per hour) ← DoS protection here, not HMAC
   c. Generate token: secrets.token_urlsafe(32)  ← 256-bit random, no signing
   d. Store in DynamoDB: { token, email, expires_at, used: false, ttl }
   e. Send email with link: /auth/verify/<token>
4. User clicks link
5. GET /api/v2/auth/magic-link/verify/<token>

**SECURITY**: Token in path, NOT query string. Query params leak via:
- Referer headers to external resources
- Browser history
- Server access logs
- URL sharing/copy-paste accidents

**CRITICAL (A5)**: Endpoint MUST reject `?token=` query params:
```python
# src/lambdas/dashboard/auth.py - magic link verify endpoint

async def verify_magic_link(request: Request, token: str = Path(...)):
    """
    Verify magic link token.

    A5 FIX: REJECT query string tokens to prevent leakage.
    """
    # A5 FIX: Explicitly reject query param tokens
    if "token" in request.query_params:
        logger.warning(
            "magic_link_query_param_rejected",
            ip=request.client.host,
            query_params=list(request.query_params.keys()),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": "AUTH_011",
                "message": "Token must be in URL path, not query string",
            }
        )

    # Continue with path-based token verification...
    return await consume_magic_link_token(token)
```

6. Backend (ATOMIC - single DynamoDB call):
   response = table.update_item(
       Key={"PK": f"MAGIC_LINK#{token}"},
       UpdateExpression="SET used = :true, used_at = :now",
       ConditionExpression="used = :false AND expires_at > :now",
       ExpressionAttributeValues={...},
       ReturnValues="ALL_NEW",
   )
   a. If ConditionalCheckFailedException: token invalid/expired/used → 410 Gone
   b. If success: token was valid, now consumed atomically
   c. Create/find user by email from returned item
   d. If anonymous_user_id: merge data
   e. Issue tokens (access in body, refresh in cookie)
7. Frontend stores access_token in memory
```

### Token Storage (DynamoDB)

```python
# src/lambdas/shared/models/magic_link_token.py (SIMPLIFIED - no signature)
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class MagicLinkToken:
    token: str                  # secrets.token_urlsafe(32), partition key
    email: str                  # Target email
    created_at: datetime
    expires_at: datetime        # created_at + 1 hour
    used: bool = False          # One-time use flag
    used_at: datetime | None = None    # Audit: when consumed
    used_by_ip: str | None = None      # Audit: from where
    anonymous_user_id: str | None = None  # For account merge
    ttl: int = 0                # DynamoDB TTL: expires_at + 24h

    @classmethod
    def create(cls, email: str, anonymous_user_id: str | None = None) -> "MagicLinkToken":
        now = datetime.utcnow()
        expires = now + timedelta(hours=1)
        return cls(
            token=secrets.token_urlsafe(32),  # 256-bit entropy, URL-safe
            email=email,
            created_at=now,
            expires_at=expires,
            anonymous_user_id=anonymous_user_id,
            ttl=int((expires + timedelta(hours=24)).timestamp()),
        )
```

### Migration: Remove MAGIC_LINK_SECRET

Since we're removing HMAC, the `MAGIC_LINK_SECRET` environment variable is no longer needed.

```python
# BEFORE (auth.py:1101-1103) - DELETE THIS
MAGIC_LINK_SECRET = os.environ.get(
    "MAGIC_LINK_SECRET", "default-dev-secret-change-in-prod"
)

# AFTER - No secret needed for magic links
# Token security comes from:
# 1. 256-bit random token (unguessable)
# 2. Atomic consumption (no replay)
# 3. Short expiry (1 hour)
# 4. Rate limiting (5 per email per hour)
```

**Terraform cleanup**: Remove `MAGIC_LINK_SECRET` from Lambda environment variables and Secrets Manager.

---

## Refresh Token Cookie Settings

### Production Settings

```python
REFRESH_COOKIE_SETTINGS = {
    "key": "refresh_token",
    "httponly": True,           # JS cannot read
    "secure": True,             # HTTPS only
    "samesite": "strict",       # Not sent on cross-origin requests
    "path": "/api/v2/auth/refresh",  # v2.8: Narrowed to refresh endpoint only
    "max_age": 604800,          # 7 days
}
```

**Note**: Backend currently uses `samesite="strict"`. This is MORE restrictive than v1 spec said (`Lax`).

**Implication**: OAuth redirects work because:
1. User is redirected TO Cognito (cookie not needed)
2. User is redirected BACK (GET request, cookie not sent due to Strict)
3. Frontend makes POST to `/api/v2/auth/oauth/callback` (same-origin, cookie sent)

This is correct. No change needed.

---

## Concurrent Refresh Handling (NEW)

### Problem

Two API requests get 401 simultaneously. Both call `/refresh`. Race condition.

### Solution: Client-Side Request Deduplication

```typescript
// frontend/src/lib/api/client.ts

let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  // If refresh already in progress, wait for it
  if (refreshPromise) {
    return refreshPromise;
  }

  // Start new refresh
  refreshPromise = doRefresh();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

async function doRefresh(): Promise<boolean> {
  try {
    const response = await fetch('/api/v2/auth/refresh', {
      method: 'POST',
      credentials: 'include',
    });

    if (!response.ok) return false;

    const { access_token, user } = await response.json();
    useAuthStore.getState().setAuth(access_token, user);
    return true;
  } catch {
    return false;
  }
}
```

### Server-Side: Atomic Refresh Token Rotation (REQUIRED)

Backend MUST handle concurrent refresh atomically:

```python
# src/lambdas/dashboard/auth.py - refresh_tokens()

async def refresh_tokens(request: Request) -> Response:
    """
    Refresh access token using httpOnly cookie.

    ATOMIC: Uses DynamoDB conditional update to prevent:
    - Double-spending of refresh tokens
    - Token proliferation from concurrent requests
    """
    # 1. Extract refresh token from httpOnly cookie
    refresh_token = extract_refresh_token_from_cookie(request)
    if not refresh_token:
        raise HTTPException(401, "No refresh token")

    # 2. Hash token for storage lookup (never store plaintext)
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    # 3. Generate new tokens
    new_refresh_token = secrets.token_urlsafe(32)
    new_token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
    now = datetime.now(UTC)

    # 4. ATOMIC rotation: only succeeds if old token still valid
    try:
        response = table.update_item(
            Key={"PK": f"REFRESH#{token_hash}"},
            UpdateExpression="""
                SET token_hash = :new_hash,
                    rotated_at = :now,
                    previous_hash = :old_hash
                REMOVE #ttl
            """,
            ConditionExpression="attribute_exists(PK) AND revoked_at = :null",
            ExpressionAttributeNames={"#ttl": "ttl"},
            ExpressionAttributeValues={
                ":new_hash": new_token_hash,
                ":now": now.isoformat(),
                ":old_hash": token_hash,
                ":null": None,
            },
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            # Token was already rotated or revoked
            # Could be: (a) concurrent request, (b) stolen token
            # Log for security monitoring, return 401
            logger.warning(f"Refresh token rotation failed: {token_hash[:8]}...")
            raise HTTPException(401, "Invalid refresh token")
        raise

    # 5. Get user from rotated token record
    user_id = response["Attributes"]["user_id"]
    user = await get_user(user_id)

    # 6. Generate new access token
    access_token = create_access_token(user)

    # 7. Return with new cookie
    resp = JSONResponse({"access_token": access_token, "user": user.to_dict()})
    resp.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        **REFRESH_COOKIE_SETTINGS,
    )
    return resp
```

**Concurrency Behavior:**
| Scenario | Request 1 | Request 2 | Result |
|----------|-----------|-----------|--------|
| Normal (sequential) | 200 + new token | 200 + new token | Both work |
| Concurrent (same token) | 200 + new token | 401 (token rotated) | One wins |
| Stolen token reused | 401 | 401 | Both fail (security) |

**Error Codes:**
- `200`: Refresh successful, new access + refresh tokens issued
- `401`: Token invalid, revoked, or already rotated (re-login required)
- `429`: Rate limited (future - see Rate Limiting section)

**Security Note**: Hashing refresh tokens before storage prevents database breach from exposing valid tokens.

---

## API Endpoints

### Auth Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v2/auth/anonymous` | POST | None | Create anonymous session |
| `/api/v2/auth/magic-link` | POST | None | Request magic link email |
| `/api/v2/auth/magic-link/verify/<token>` | GET | Path param | Verify magic link (no HMAC sig) |
| `/api/v2/auth/oauth/urls` | GET | None | Get OAuth provider URLs |
| `/api/v2/auth/oauth/callback` | POST | Query param code | Exchange OAuth code |
| `/api/v2/auth/refresh` | POST | httpOnly cookie | Get new access token |
| `/api/v2/auth/signout` | POST | Bearer token | Clear session + revoke refresh token |
| `/api/v2/auth/session` | GET | Bearer token | Get session info |
| `/api/v2/auth/validate` | GET | Bearer token | Validate current session |
| `/api/v2/auth/link-accounts` | POST | Bearer token | Link anonymous to auth |
| `/api/v2/admin/sessions/revoke` | POST | **MUST ADD @require_role("operator")** | Bulk revocation |

### OAuth Security (A8 FIX - State Validation)

**Problem**: OAuth callback without state validation allows CSRF attacks.
Attacker can make user click link with attacker's authorization code,
logging user into attacker's account (session fixation).

**REQUIRED** (per RFC 6749 Section 10.12):

```python
# src/lambdas/dashboard/auth.py - OAuth flow

import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request, Response

# A8 FIX: State parameter for OAuth CSRF protection
def generate_oauth_state() -> str:
    """Generate cryptographically random state parameter."""
    return secrets.token_urlsafe(32)


async def initiate_oauth(request: Request, response: Response, provider: str):
    """
    Start OAuth flow with state parameter.

    A8 FIX: State MUST be:
    1. Cryptographically random (256-bit)
    2. Stored server-side (DynamoDB or signed cookie)
    3. Validated on callback before code exchange
    """
    state = generate_oauth_state()

    # Store state with TTL (5 min max for OAuth flow)
    await store_oauth_state(
        state=state,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    # Build OAuth URL with state
    oauth_url = build_oauth_url(
        provider=provider,
        redirect_uri=f"{settings.API_URL}/api/v2/auth/oauth/callback",
        state=state,  # CRITICAL: Include state in redirect
    )

    return {"url": oauth_url}


async def oauth_callback(request: Request, code: str, state: str):
    """
    Handle OAuth callback.

    A8 FIX: Validate state BEFORE exchanging code.
    """
    # A8 FIX: State validation (MUST be first check)
    stored_state = await consume_oauth_state(state)  # Atomic, one-time use

    if not stored_state:
        logger.warning(
            "oauth_state_invalid",
            ip=request.client.host,
            state_preview=state[:8] + "..." if state else None,
        )
        raise HTTPException(
            status_code=400,
            detail={"code": "AUTH_012", "message": "Invalid OAuth state"},
        )

    # State valid, proceed with code exchange
    tokens = await exchange_oauth_code(code)
    user = await get_or_create_user_from_oauth(tokens)

    # Issue our tokens
    return await complete_login(user, request)
```

**State Storage (DynamoDB)**:
```
PK: OAUTH_STATE#<state>
Attributes:
  - ip: string
  - user_agent: string
  - created_at: ISO8601
  - expires_at: ISO8601
  - ttl: number (DynamoDB TTL)
```

**Why state validation matters**:
- Without state: Attacker generates valid OAuth code for their account
- Attacker tricks victim into clicking callback URL with attacker's code
- Victim gets logged into attacker's account
- Attacker now sees victim's activity in "their" account

### Token Response Format

All auth endpoints that issue tokens return:

```json
{
  "access_token": "eyJhbG...",
  "user": {
    "id": "user-123",
    "email": "user@example.com",
    "roles": ["authenticated"]
  }
}
```

Plus `Set-Cookie` header for refresh token.

**Note for anonymous users:**
```json
{
  "access_token": "eyJhbG...",
  "user": {
    "id": "anon-456",
    "email": null,
    "roles": ["anonymous"]
  }
}
```

### Signout Behavior (NEW - CLARIFIED)

`POST /api/v2/auth/signout` MUST do BOTH:

1. **Clear cookie** - Set expired `Set-Cookie` header:
   ```
   Set-Cookie: refresh_token=; Path=/api/v2/auth/refresh; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; Secure; SameSite=Strict
   ```
   **v2.8 Note**: Path MUST match the path used when setting cookie (`/api/v2/auth/refresh`).

2. **Revoke server-side** - Invalidate session by JWT session_id (NOT cookie):
   ```python
   # src/lambdas/dashboard/auth.py
   async def signout(request: Request):
       """
       Signout using JWT session_id, not refresh token cookie.

       v2.8 CHANGE: Cookie path is /api/v2/auth/refresh, so signout
       endpoint won't receive the cookie. Use JWT sid claim instead.

       Requires: Authorization: Bearer <access_token> header
       """
       # Extract session_id from JWT (not from cookie)
       auth_header = request.headers.get("Authorization", "")
       if not auth_header.startswith("Bearer "):
           raise HTTPException(401, "Access token required for signout")

       token = auth_header[7:]
       payload = await validate_jwt_global(token)
       if not payload:
           raise HTTPException(401, "Invalid access token")

       session_id = payload.get("sid")
       if session_id:
           await revoke_session(payload["sub"], session_id, reason="user_signout")

       response = JSONResponse({"success": True})
       response.delete_cookie(
           key="refresh_token",
           path="/api/v2/auth/refresh",  # v2.8: Must match set path
           httponly=True,
           secure=True,
           samesite="strict",
       )
       return response
   ```

**Why JWT-based signout (v2.8)?**
- Cookie path `/api/v2/auth/refresh` means signout endpoint doesn't receive cookie
- Using JWT sid is MORE secure: requires valid access token to sign out
- Prevents anonymous session termination attacks
- Session revocation uses sid claim, not refresh token hash

**Why server-side revocation?**
- Cookie can be extracted before logout (XSS, malware, shoulder surfing)
- Without server revocation, stolen token remains valid until expiry (7 days)
- With revocation, stolen token immediately rejected

**Implementation options**:
1. **Allowlist** - Store valid tokens, delete on logout (preferred)
2. **Blocklist** - Store revoked tokens, check on refresh (requires TTL cleanup)

### Token Revocation Garbage Collection (A9 FIX)

**Problem**: Blocklist strategy causes unbounded table growth.
Each logout, password change, or session eviction adds entries.
Without cleanup, DynamoDB storage costs scale linearly with user activity.

**Strategy**: Use DynamoDB TTL with safe deletion window.

```python
# src/lambdas/shared/auth/revocation.py

# A9 FIX: TTL must exceed maximum token lifetime
REVOCATION_TTL_SECONDS = (
    7 * 24 * 60 * 60  # Refresh token max age (7 days)
    + 24 * 60 * 60    # Safe buffer (24 hours)
)  # = 8 days total


async def revoke_refresh_token(token_hash: str, reason: str):
    """
    Add token to revocation list with auto-expiring TTL.

    A9 FIX: Entry auto-deletes after token would have expired anyway.
    """
    now = datetime.now(UTC)
    ttl = int((now + timedelta(seconds=REVOCATION_TTL_SECONDS)).timestamp())

    await table.put_item(
        Item={
            "PK": f"REVOKED#{token_hash}",
            "revoked_at": now.isoformat(),
            "reason": reason,  # "logout", "password_change", "session_evicted", "admin_revoke"
            "ttl": ttl,  # DynamoDB auto-deletes after 8 days
        }
    )


async def is_token_revoked(token_hash: str) -> bool:
    """Check if token is in revocation list."""
    response = await table.get_item(Key={"PK": f"REVOKED#{token_hash}"})
    return "Item" in response
```

**DynamoDB Configuration**:
```hcl
# infrastructure/terraform/modules/dynamodb/main.tf

resource "aws_dynamodb_table" "auth_tokens" {
  # ... existing config ...

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}
```

**Cost Analysis**:
- Without TTL: ~10KB per revocation * 1000 users * 10 logouts/year = 100MB/year growth
- With TTL: Max 8 days of data, ~10KB * 1000 users * ~3 active entries = 30MB steady-state

**Alternative (Preferred)**: Use allowlist pattern instead:
- Store only VALID sessions
- Delete on logout (no TTL needed)
- Query is "does session exist?" not "is session revoked?"
- No garbage collection required

---

## Frontend Implementation

### Files to DELETE

| File | Reason |
|------|--------|
| `frontend/src/lib/cookies.ts` | Sets non-httpOnly cookies. Server sets httpOnly. |

### Files to REWRITE

#### auth-store.ts (No Persistence)

```typescript
// frontend/src/stores/auth-store.ts
import { create } from 'zustand';
// NO persist middleware - tokens live in memory only

interface User {
  id: string;
  email: string | null;
  roles: string[];
}

interface AuthState {
  // State
  accessToken: string | null;
  user: User | null;
  isLoading: boolean;
  isInitialized: boolean;
  error: string | null;
}

interface AuthActions {
  // Actions
  setAuth: (token: string, user: User) => void;
  clearAuth: () => void;
  setLoading: (loading: boolean) => void;
  setInitialized: () => void;
  setError: (error: string | null) => void;

  // Computed getters
  isAuthenticated: () => boolean;
  isAnonymous: () => boolean;
  hasRole: (role: string) => boolean;
}

export const useAuthStore = create<AuthState & AuthActions>((set, get) => ({
  // Initial state
  accessToken: null,
  user: null,
  isLoading: false,
  isInitialized: false,
  error: null,

  // Computed
  isAuthenticated: () => get().accessToken !== null,
  isAnonymous: () => get().user?.roles.includes('anonymous') ?? false,
  hasRole: (role: string) => get().user?.roles.includes(role) ?? false,

  // Actions
  setAuth: (token, user) => set({
    accessToken: token,
    user,
    error: null,
  }),

  clearAuth: () => set({
    accessToken: null,
    user: null,
  }),

  setLoading: (loading) => set({ isLoading: loading }),
  setInitialized: () => set({ isInitialized: true }),
  setError: (error) => set({ error }),
}));
```

**Key difference from current**: NO `persist` middleware. Token lives in memory only.

#### client.ts (With Retry and Deduplication)

```typescript
// frontend/src/lib/api/client.ts
import { useAuthStore } from '@/stores/auth-store';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

// Singleton refresh promise for deduplication
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v2/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) return false;

      const { access_token, user } = await response.json();
      useAuthStore.getState().setAuth(access_token, user);
      return true;
    } catch {
      return false;
    }
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

export class ApiClient {
  private getAuthHeader(): Record<string, string> {
    const token = useAuthStore.getState().accessToken;
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  }

  async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE}${path}`;

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeader(),
        ...options.headers,
      },
      credentials: 'include',
    });

    // Handle 401: try refresh once
    if (response.status === 401) {
      const refreshed = await tryRefresh();
      if (refreshed) {
        // Retry original request with new token
        return this.request(path, options);
      }
      // Refresh failed - clear auth
      useAuthStore.getState().clearAuth();
      throw new ApiError(401, 'SESSION_EXPIRED', 'Session expired');
    }

    // Handle 403: roles insufficient (don't retry)
    if (response.status === 403) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(403, 'FORBIDDEN', error.detail || 'Access denied');
    }

    // Handle other errors
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.code || 'UNKNOWN_ERROR',
        error.detail || 'Request failed'
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  get<T>(path: string) {
    return this.request<T>(path, { method: 'GET' });
  }

  post<T>(path: string, body?: unknown) {
    return this.request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  put<T>(path: string, body: unknown) {
    return this.request<T>(path, {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  }

  delete<T>(path: string) {
    return this.request<T>(path, { method: 'DELETE' });
  }
}

export const apiClient = new ApiClient();

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
```

#### use-session-init.ts (Cookie-Based Restore)

```typescript
// frontend/src/hooks/use-session-init.ts
import { useEffect, useRef } from 'react';
import { useAuthStore } from '@/stores/auth-store';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const INIT_TIMEOUT_MS = 10000;

export function useSessionInit() {
  const initAttempted = useRef(false);
  const {
    isInitialized,
    setAuth,
    clearAuth,
    setLoading,
    setInitialized,
    setError
  } = useAuthStore();

  useEffect(() => {
    // Only run once
    if (isInitialized || initAttempted.current) return;
    initAttempted.current = true;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), INIT_TIMEOUT_MS);

    const init = async () => {
      setLoading(true);

      try {
        // Try to restore session via httpOnly cookie
        const response = await fetch(`${API_BASE}/api/v2/auth/refresh`, {
          method: 'POST',
          credentials: 'include',
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (response.ok) {
          const { access_token, user } = await response.json();
          setAuth(access_token, user);
        } else if (response.status === 401) {
          // No valid session - expected for new users
          clearAuth();
        } else if (response.status === 429) {
          // Rate limited
          const retryAfter = response.headers.get('Retry-After') || '60';
          setError(`Too many requests. Try again in ${retryAfter}s`);
          clearAuth();
        } else {
          // Server error
          setError('Failed to restore session');
          clearAuth();
        }
      } catch (error) {
        clearTimeout(timeoutId);

        if (error instanceof Error && error.name === 'AbortError') {
          setError('Session restore timed out');
        } else {
          setError('Network error during session restore');
        }
        clearAuth();
      } finally {
        setLoading(false);
        setInitialized();
      }
    };

    init();

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [isInitialized, setAuth, clearAuth, setLoading, setInitialized, setError]);

  return {
    isLoading: useAuthStore((s) => s.isLoading),
    isInitialized: useAuthStore((s) => s.isInitialized),
    error: useAuthStore((s) => s.error),
  };
}
```

---

## Browser Scenarios

### Page Refresh

1. React app mounts
2. `useSessionInit` calls `POST /api/v2/auth/refresh`
3. Browser automatically sends httpOnly cookie
4. If valid: new access_token returned, stored in memory
5. If invalid/expired: 401 returned, user sees login prompt

### New Tab

Same as page refresh. Each tab has its own memory. Cookie shared.

### Browser Close + Reopen

1. In-memory access_token is lost (expected)
2. httpOnly cookie persists (7-day Max-Age)
3. On page load, `/refresh` restores session
4. User stays logged in

### Incognito/Private Mode

1. Cookies may be cleared on window close (browser-dependent)
2. Session lost when incognito window closes
3. User sees login prompt on next visit
4. This is acceptable and expected.

### Multi-Tab Logout

1. Tab A calls `/signout`
2. Server clears httpOnly cookie
3. Tab B still has in-memory access_token
4. Tab B continues working until token expires (15 min max)
5. Tab B's next refresh fails, user sees login prompt

**Acceptable limitation**. Cross-tab sync via BroadcastChannel is out of scope.

### Back Button After Logout (NEW - SECURITY)

**Problem**: User logs out, presses back button, sees cached protected content.

**Solution**: All protected pages MUST include cache-busting headers:

```python
# src/lambdas/dashboard/middleware/security_headers.py
def add_security_headers(response: Response) -> Response:
    """Add security headers to prevent back-button cache exposure."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
```

**Frontend**: Next.js middleware should set headers for protected routes:

```typescript
// frontend/src/middleware.ts
if (isProtectedRoute(request.nextUrl.pathname)) {
  response.headers.set("Cache-Control", "no-store, no-cache, must-revalidate, private");
  response.headers.set("Pragma", "no-cache");
  response.headers.set("Expires", "0");
}
```

**Verification**: After logout, back button shows login page, not cached content.

### Network Failure During Refresh (NEW)

**Problem**: Refresh request fails mid-flight. User stuck in indeterminate state.

**Solution**: `tryRefresh()` must have timeout and proper error handling:

```typescript
// frontend/src/lib/api/client.ts
async function tryRefresh(): Promise<boolean> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000); // 5s timeout

  try {
    const response = await fetch("/api/v2/auth/refresh", {
      method: "POST",
      credentials: "include",
      signal: controller.signal,
    });
    clearTimeout(timeout);
    return response.ok;
  } catch (error) {
    clearTimeout(timeout);
    if (error instanceof DOMException && error.name === "AbortError") {
      console.warn("Refresh timeout - treating as expired");
    }
    return false; // Treat as expired, show login
  }
}
```

---

## Migration Path

### Phase 0: Critical Security Fixes (MUST DO FIRST)

**These fixes MUST be deployed before ANY other work. They address vulnerabilities in production.**

| # | Severity | File | Line | Issue | Fix |
|---|----------|------|------|-------|-----|
| C1 | CRITICAL | `auth.py` | 1101-1103 | Hardcoded fallback secret | DELETE - switch to random tokens |
| C2 | HIGH | `auth.py` | 1510-1529 | Mock tokens in prod | Add Lambda environment guard |
| C3 | HIGH | `auth.py` | 1438-1443 | Non-atomic token use | Use conditional update |
| C4 | CRITICAL | `router_v2.py` | 517-532 | `/admin/sessions/revoke` unprotected | Add `@require_role("admin")` |
| C5 | HIGH | `router_v2.py` | 673-705 | `/users/lookup` unprotected | Add `@require_role("admin")` |
| C6 | HIGH | `auth-store.ts` | 57,276 | Tokens in localStorage | Remove zustand persist |
| C6b | HIGH | `cookies.ts` | 13 | Non-httpOnly cookie | DELETE entire file |

**Fix C1: Remove HMAC secret (switch to random tokens)**

```python
# BEFORE (VULNERABLE) - auth.py:1101-1103
MAGIC_LINK_SECRET = os.environ.get(
    "MAGIC_LINK_SECRET", "default-dev-secret-change-in-prod"
)

# AFTER (SECURE - no secret needed)
# DELETE the above lines entirely
# Replace HMAC-based token generation with:
import secrets
token = secrets.token_urlsafe(32)  # 256-bit random, unguessable

# See "Magic Link (Simplified Architecture)" section for full implementation
```

**Fix 2: Guard mock tokens**

```python
# BEFORE (VULNERABLE)
def _generate_tokens(user: User) -> tuple[dict, str]:
    """Generate mock tokens for testing."""
    refresh_token = f"mock_refresh_token_{user.user_id[:8]}"
    ...

# AFTER (SECURE - explicit environment check)
def _generate_tokens(user: User) -> tuple[dict, str]:
    """Generate mock tokens for testing only."""
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        raise RuntimeError("Mock tokens cannot be generated in Lambda environment")
    refresh_token = f"mock_refresh_token_{user.user_id[:8]}"
    ...
```

**Fix 3: Atomic token consumption**

```python
# BEFORE (RACE CONDITION in verify_magic_link)
token = self.table.get_item(Key={"token_id": token_id})["Item"]
if token["used"]:
    return None
self.table.update_item(Key={"token_id": token_id}, ...)

# AFTER (ATOMIC - copy pattern from verify_and_consume_token)
response = self.table.update_item(
    Key={"token_id": token_id},
    UpdateExpression="SET used = :true",
    ConditionExpression="used = :false AND expires_at > :now",
    ExpressionAttributeValues={
        ":true": True,
        ":false": False,
        ":now": int(time.time()),
    },
    ReturnValues="ALL_NEW",
)
```

**Fix C4: Protect /admin/sessions/revoke**

```python
# BEFORE (VULNERABLE) - router_v2.py:517-532
@router.post("/admin/sessions/revoke")
async def revoke_sessions(...):
    # Any user can call this!
    ...

# AFTER (SECURE)
from src.lambdas.shared.middleware.require_role import require_role

@router.post("/admin/sessions/revoke")
@require_role("admin")
async def revoke_sessions(...):
    ...
```

**Fix C5: Protect /users/lookup**

```python
# BEFORE (VULNERABLE) - router_v2.py:673-705
@router.get("/users/lookup")
async def lookup_user(...):
    # User enumeration attack vector!
    ...

# AFTER (SECURE)
@router.get("/users/lookup")
@require_role("admin")
async def lookup_user(...):
    ...
```

**Fix C6: Remove frontend token exposure**

```typescript
// C6a: auth-store.ts - Remove persist middleware
// BEFORE (VULNERABLE)
export const useAuthStore = create<AuthState>()(
  persist(  // ❌ REMOVE THIS
    (set, get) => ({...}),
    { name: 'sentiment-auth-tokens' }  // ❌ Writes to localStorage
  )
);

// AFTER (SECURE) - Memory only
export const useAuthStore = create<AuthState>((set, get) => ({...}));

// C6b: DELETE frontend/src/lib/cookies.ts entirely
// This file sets non-httpOnly cookies that XSS can read
```

**Deployment Order**: C1 → C2 → C3 → C4 → C5 → C6 (each as separate commit)

### Phase 1: Backend (Non-Breaking)

1. **Add secrets module** (`src/lambdas/shared/config/secrets.py`)
   - `get_jwt_secret()` - fails if not configured
   - NOTE: `get_magic_link_secret()` NOT needed (v2.3: random tokens, no HMAC)

2. **Add JWT generation module** (`src/lambdas/shared/auth/jwt.py`)
   - `create_access_token(user)` - generates JWT with all required claims
   - `create_refresh_token()` - generates random token + hash pair

3. **Delete MAGIC_LINK_SECRET** in `auth.py:1101-1103`
   - Remove entire hardcoded fallback (already done in Phase 0 C1)
   - Magic links now use `secrets.token_urlsafe(32)` (no secret needed)

4. **Guard mock token generation** in `auth.py:1510-1529`
   - Add `if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):` guard
   - Production Lambda must use real Cognito tokens only

5. **Add @require_role decorator**
   - Create `src/lambdas/shared/middleware/require_role.py`
   - Apply to `/admin/sessions/revoke` endpoint
   - Apply to `/users/lookup` endpoint

6. **Keep existing auth working** during transition
   - Both header patterns continue to work
   - No breaking changes yet

### Phase 1.5: RBAC Infrastructure (Foundation for paid/operator)

**Purpose**: Establish role infrastructure before it's needed. Zero additional complexity for current users.

#### 1. Role Enum and Model Updates

```python
# src/lambdas/shared/models/role.py (NEW FILE)
from enum import Enum

class Role(str, Enum):
    """
    User roles. Additive (users can have multiple).

    Current:
      - FREE: Default for all authenticated users
      - ANONYMOUS: Unauthenticated temporary session

    Future (schema ready, assignment API not implemented):
      - PAID: Active subscription
      - OPERATOR: Can manage other users
      - ADMIN: Full system access
    """
    ANONYMOUS = "anonymous"
    FREE = "free"           # Default for authenticated
    PAID = "paid"           # Future: subscription active
    OPERATOR = "operator"   # Future: user management
    ADMIN = "admin"         # Future: system administration


def get_roles_for_user(user: "User") -> list[str]:
    """
    Determine roles based on user state.

    Current: Returns [ANONYMOUS] or [FREE] based on auth_type.
    Future: Will check subscription_active, is_operator, is_admin fields.
    """
    if user.auth_type == "anonymous":
        return [Role.ANONYMOUS.value]

    roles = [Role.FREE.value]

    # Future fields (not yet in User model)
    if getattr(user, "subscription_active", False):
        roles.append(Role.PAID.value)
    if getattr(user, "is_operator", False):
        roles.append(Role.OPERATOR.value)
    if getattr(user, "is_admin", False):
        roles.append(Role.ADMIN.value)

    return roles
```

#### 2. User Model Extension (Schema Only)

```python
# src/lambdas/shared/models/user.py - ADD fields (nullable, no migration needed)

class User(BaseModel):
    # ... existing fields ...

    # RBAC fields (Phase 1.5 - schema ready, assignment API in Phase 3+)
    role: str = "free"                    # Primary role for quick checks
    subscription_active: bool = False     # Future: billing integration
    subscription_expires_at: datetime | None = None
    is_operator: bool = False             # Future: admin console
    is_admin: bool = False                # Future: system admin
```

#### 3. DynamoDB Schema Extension

```hcl
# infrastructure/terraform/modules/dynamodb/main.tf - ADD attribute

# No migration needed - DynamoDB is schemaless
# New items will have role field, old items default to "free" in code

# Optional: GSI for role-based queries (defer until needed)
# global_secondary_index {
#   name            = "role-index"
#   hash_key        = "role"
#   projection_type = "KEYS_ONLY"
# }
```

#### 4. JWT Claims Extension

```python
# When generating JWT, include role
claims = {
    "sub": user.user_id,
    "email": user.email,
    "roles": get_roles_for_user(user),  # ["free"] or ["anonymous"]
    "iat": now,
    "exp": now + ACCESS_TOKEN_LIFETIME,
    "nbf": now,
    "iss": "sentiment-analyzer",
    "aud": "sentiment-analyzer-api",
}
```

#### 5. Backward Compatibility

- Existing users: `role` field absent → code treats as `"free"`
- Existing JWTs: `roles` claim absent → code treats as `["authenticated"]`
- No database migration required
- No breaking changes to API

#### Phase 1.5 Success Criteria

1. ✅ Role enum exists with all planned roles
2. ✅ User model has role fields (nullable)
3. ✅ `get_roles_for_user()` returns correct roles
4. ✅ JWTs include `roles` claim
5. ✅ `@require_role` decorator works with all roles
6. ✅ All existing tests pass (no behavior change)

### Phase 2: Frontend (Breaking)

1. **Delete** `frontend/src/lib/cookies.ts`

2. **Rewrite** `auth-store.ts`
   - Remove `persist` middleware
   - Remove localStorage references
   - Memory-only token storage

3. **Rewrite** `client.ts`
   - Add refresh deduplication
   - Add 401 auto-refresh-retry
   - Remove X-User-ID header fallback

4. **Rewrite** `use-session-init.ts`
   - Cookie-based restore only
   - No localStorage hydration

5. **Update** `protected-route.tsx`
   - Use new store API

6. **Update** middleware.ts
   - Remove cookie checks (rely on API for auth)
   - Keep security headers

### Phase 3: Backend Cleanup

1. **Remove** X-User-ID header support
2. **Remove** mock token generation (or move to test fixtures)
3. **Add** `@require_role` to all protected endpoints
4. **Add** rate limiting to `/refresh` endpoint

---

## Files to Modify

### Backend

| File | Action | Description |
|------|--------|-------------|
| `src/lambdas/shared/config/secrets.py` | **CREATE** | Secret management |
| `src/lambdas/shared/config/jwt_config.py` | **CREATE** | JWT configuration |
| `src/lambdas/shared/middleware/require_role.py` | **CREATE** | Role decorator |
| `src/lambdas/shared/middleware/jwt.py` | **CREATE** | JWT validation |
| `src/lambdas/dashboard/auth.py` | **MODIFY** | Use secrets module, guard mocks |
| `src/lambdas/dashboard/router_v2.py` | **MODIFY** | Add @require_role decorators |

### Frontend

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/lib/cookies.ts` | **DELETE** | No longer needed |
| `frontend/src/stores/auth-store.ts` | **REWRITE** | No persist |
| `frontend/src/lib/api/client.ts` | **REWRITE** | Dedup + retry |
| `frontend/src/hooks/use-session-init.ts` | **REWRITE** | Cookie restore |
| `frontend/src/components/auth/protected-route.tsx` | **MODIFY** | New store |
| `frontend/src/middleware.ts` | **MODIFY** | Remove cookie auth |
| `frontend/src/lib/api/auth.ts` | **SIMPLIFY** | Remove token handling |

### Infrastructure

| File | Action | Description |
|------|--------|-------------|
| `infrastructure/terraform/modules/secrets/` | **CREATE** | Secrets Manager resources |
| `infrastructure/terraform/modules/lambda/main.tf` | **MODIFY** | Add secrets IAM policy |

---

## Success Criteria

### Token Storage (S1-S4)
1. No tokens in localStorage or sessionStorage
2. No tokens in JavaScript-accessible cookies
3. Refresh token ONLY in httpOnly cookie
4. Access token ONLY in memory (JS variable)

### API Behavior (S5-S7)
5. All API requests use `Authorization: Bearer` header
6. Token refresh works via httpOnly cookie only
7. Session restored on page reload via silent refresh

### Access Control (S8-S10)
8. All protected endpoints use `@require_role` decorator
9. 401 for missing/invalid token
10. 403 for insufficient roles (error message MUST NOT leak required roles)

### Security (S11-S17)
11. No hardcoded secrets (fails HARD if env not configured)
12. Concurrent refresh requests deduplicated (singleton promise)
13. JWT includes and validates `aud` and `nbf` claims
14. Refresh tokens hashed before storage (SHA-256)
15. Atomic refresh token rotation (DynamoDB conditional update)
16. No X-User-ID header fallback (Bearer tokens only)
17. `cookies.ts` file deleted (no JS-accessible cookie writes)

### Drift Resolution (S18-S21) - v2.4
18. D1 resolved: zustand persist middleware removed
19. D2 resolved: HMAC code deleted, random tokens implemented
20. D3 resolved: aud/nbf validation added to middleware
21. D4 resolved: cookies.ts file deleted

### Blind Spots (S22-S24) - v2.4
22. B2 handled: Private browsing displays warning, graceful degradation
23. B3 ready: JWT secret rotation supports dual-secret validation
24. B7 handled: Clock skew leeway documented (60s for iat/nbf)

---

## Rate Limiting (v2.3 - Previously Missing)

Rate limiting provides DoS protection and is REQUIRED for auth endpoints.

### Implementation Strategy

**API Gateway Level** (Recommended for simplicity):
```hcl
# infrastructure/terraform/modules/api_gateway/main.tf
resource "aws_api_gateway_usage_plan" "auth" {
  name = "auth-rate-limit"

  api_stages {
    api_id = aws_apigatewayv2_api.main.id
    stage  = aws_apigatewayv2_stage.main.stage_name
  }

  throttle_settings {
    burst_limit = 50   # Max concurrent requests
    rate_limit  = 100  # Requests per second
  }
}
```

### Endpoint-Specific Limits

| Endpoint | Limit | Window | Key | Reason |
|----------|-------|--------|-----|--------|
| `/api/v2/auth/magic-link` | 5 | 1 hour | email | Prevent spam, enumeration |
| `/api/v2/auth/magic-link/verify` | 10 | 1 min | IP | Brute-force protection |
| `/api/v2/auth/refresh` | 30 | 1 min | user_id | Prevent token farming |
| `/api/v2/auth/anonymous` | 100 | 1 min | IP | Prevent session exhaustion |
| `/api/v2/auth/oauth/*` | 20 | 1 min | IP | OAuth abuse protection |
| `/api/v2/auth/signout` | 10 | 1 min | user_id | Prevent logout DOS (A11 FIX) |
| `/api/v2/auth/session` | 60 | 1 min | user_id | Prevent session enumeration (A11 FIX) |
| `/api/v2/auth/link-accounts` | 5 | 1 hour | user_id | Prevent brute-force merge (A11 FIX) |
| `/api/v2/auth/validate` | 120 | 1 min | user_id | Allow frequent polling (A11 FIX) |

### Lambda-Level Rate Limiting (Fine-Grained)

For per-email or per-user limits not expressible in API Gateway:

```python
# src/lambdas/shared/middleware/rate_limit.py
from datetime import datetime, timedelta
import hashlib

async def check_rate_limit(
    table,
    key: str,
    limit: int,
    window_seconds: int,
) -> bool:
    """
    Check if rate limit exceeded using DynamoDB atomic counter.

    Returns True if allowed, False if rate limited.
    """
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=window_seconds)
    key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]

    try:
        response = table.update_item(
            Key={"PK": f"RATE#{key_hash}", "SK": "COUNT"},
            UpdateExpression="""
                SET #count = if_not_exists(#count, :zero) + :one,
                    #window = if_not_exists(#window, :now),
                    #ttl = :ttl
            """,
            ConditionExpression="""
                attribute_not_exists(#window) OR
                #window > :window_start OR
                #count < :limit
            """,
            ExpressionAttributeNames={
                "#count": "count",
                "#window": "window_start",
                "#ttl": "ttl",
            },
            ExpressionAttributeValues={
                ":zero": 0,
                ":one": 1,
                ":now": now.isoformat(),
                ":window_start": window_start.isoformat(),
                ":limit": limit,
                ":ttl": int((now + timedelta(hours=1)).timestamp()),
            },
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False  # Rate limited
        raise


# Usage in magic link endpoint
@router.post("/magic-link")
async def request_magic_link(body: MagicLinkRequest, table=Depends(get_table)):
    if not await check_rate_limit(table, body.email, limit=5, window_seconds=3600):
        raise HTTPException(429, "Too many requests. Try again later.")
    # ... rest of implementation
```

### Response Headers

All rate-limited endpoints MUST return:
```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1704310800
Retry-After: 1800  # Only if 429
```

---

## Blind Spots (v2.4 - Previously Undocumented)

These edge cases were not addressed in prior versions:

### B1: Cross-Tab Auth Synchronization (v2.8 - BroadcastChannel)

#### B1.1: Token Refresh Race Condition

**Scenario**: User opens two tabs simultaneously, both find expired access token.

```
Tab 1: Finds expired token → calls /refresh → gets new tokens
Tab 2: Finds expired token → calls /refresh → gets new tokens (race)
```

**Resolution**: Server-side idempotent rotation. Both refreshes succeed, both get valid tokens.

#### B1.2: Cross-Tab Logout Synchronization (v2.8 NEW)

**Scenario**: User logs out in Tab A, Tab B still shows authenticated UI.

**Problem**: Without cross-tab sync:
- Tab B continues to show authenticated state
- Tab B's next API call may succeed (access token still valid for up to 15min)
- User expects "logout" to mean "logged out everywhere"

**v2.8 Resolution**: BroadcastChannel with localStorage fallback.

```typescript
// frontend/src/lib/auth/cross-tab-sync.ts

type AuthMessage =
  | { type: 'LOGOUT'; timestamp: number }
  | { type: 'LOGIN'; timestamp: number; userId: string }
  | { type: 'TOKEN_REFRESH'; timestamp: number };

class CrossTabAuthSync {
  private channel: BroadcastChannel | null = null;
  private lastEventTimestamp = 0;

  constructor(private onLogout: () => void, private onLogin: () => void) {
    this.init();
  }

  private init() {
    // BroadcastChannel for modern browsers
    if (typeof BroadcastChannel !== 'undefined') {
      this.channel = new BroadcastChannel('auth-sync');
      this.channel.onmessage = (e: MessageEvent<AuthMessage>) => {
        this.handleMessage(e.data);
      };
    }

    // localStorage fallback for Safari < 15.4
    window.addEventListener('storage', this.handleStorageEvent);

    // Check for missed events on tab focus
    document.addEventListener('visibilitychange', this.handleVisibilityChange);
  }

  private handleMessage(message: AuthMessage) {
    // Prevent duplicate processing
    if (message.timestamp <= this.lastEventTimestamp) return;
    this.lastEventTimestamp = message.timestamp;

    switch (message.type) {
      case 'LOGOUT':
        this.onLogout();
        break;
      case 'LOGIN':
        this.onLogin();
        break;
    }
  }

  private handleStorageEvent = (e: StorageEvent) => {
    // localStorage fallback for older Safari
    if (e.key === 'auth-logout-trigger' && e.newValue) {
      const timestamp = parseInt(e.newValue, 10);
      if (timestamp > this.lastEventTimestamp) {
        this.lastEventTimestamp = timestamp;
        this.onLogout();
      }
    }
  };

  private handleVisibilityChange = () => {
    if (document.visibilityState === 'visible') {
      // Tab became visible - check for missed logout
      const logoutTimestamp = localStorage.getItem('auth-logout-trigger');
      if (logoutTimestamp) {
        const timestamp = parseInt(logoutTimestamp, 10);
        if (timestamp > this.lastEventTimestamp) {
          this.lastEventTimestamp = timestamp;
          this.onLogout();
        }
      }
    }
  };

  broadcast(message: AuthMessage) {
    this.lastEventTimestamp = message.timestamp;

    // BroadcastChannel (primary)
    this.channel?.postMessage(message);

    // localStorage (fallback + offline tab detection)
    if (message.type === 'LOGOUT') {
      localStorage.setItem('auth-logout-trigger', message.timestamp.toString());
    }
  }

  destroy() {
    this.channel?.close();
    window.removeEventListener('storage', this.handleStorageEvent);
    document.removeEventListener('visibilitychange', this.handleVisibilityChange);
  }
}

export const crossTabSync = new CrossTabAuthSync(
  () => {
    // Force logout in this tab
    useAuthStore.getState().clearAuth();
    window.location.href = '/login?reason=session_ended';
  },
  () => {
    // Another tab logged in - refresh our state
    useAuthStore.getState().refreshFromStorage();
  }
);
```

**Usage in signout:**
```typescript
// frontend/src/stores/auth-store.ts

async signout() {
  try {
    await authApi.signout();
  } finally {
    // Clear local state
    this.clearAuth();

    // Notify other tabs
    crossTabSync.broadcast({
      type: 'LOGOUT',
      timestamp: Date.now(),
    });
  }
}
```

**Browser Compatibility:**
| Browser | BroadcastChannel | Fallback |
|---------|-----------------|----------|
| Chrome 54+ | ✅ | N/A |
| Firefox 38+ | ✅ | N/A |
| Safari 15.4+ | ✅ | N/A |
| Safari < 15.4 | ❌ | localStorage + storage event |
| Edge 79+ | ✅ | N/A |

**Edge Cases Handled:**
1. **Offline tab**: Checks localStorage on `visibilitychange`
2. **Race condition**: Uses monotonic timestamp to prevent duplicate processing
3. **Safari ITP**: localStorage survives ITP (see B8: Safari ITP Compatibility)
4. **Closed tabs**: Don't receive messages, but that's expected

### B2: Private Browsing / Anonymous Mode

**Scenario**: User in incognito mode, localStorage unavailable, cookies may be blocked.

**Current Handling (auth-store.ts:290-305)**: Falls back to memory if localStorage unavailable.

**Missing**: What happens when cookies ALSO blocked?

**Resolution**:
- If httpOnly cookies blocked: Full anonymous experience only
- No session persistence possible
- User must re-authenticate on each page load
- Display warning: "Private browsing detected - session will not persist"

**Implementation Requirement (v2.5)**:
```typescript
// frontend/src/components/auth/PrivateBrowsingWarning.tsx
export function PrivateBrowsingWarning() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    // Detect private browsing: try to use localStorage
    try {
      localStorage.setItem('__test__', '1');
      localStorage.removeItem('__test__');
    } catch {
      setShow(true);
    }
  }, []);

  if (!show) return null;

  return (
    <Toast variant="warning" onDismiss={() => setShow(false)}>
      Private browsing detected. Your session will not persist after closing this tab.
    </Toast>
  );
}
```

**Integration**: Add to `AuthProvider` component (renders on mount).

### B3: JWT Secret Rotation

**Scenario**: Need to rotate JWT secret without invalidating all active sessions.

**Current Spec (line 197)**: Single secret from Secrets Manager.

**Resolution**: Support dual-secret validation during rotation window:
```python
def validate_jwt(token: str) -> dict:
    secrets = [get_current_secret(), get_previous_secret()]
    for secret in filter(None, secrets):
        try:
            return jwt.decode(token, secret, algorithms=["HS256"], ...)
        except jwt.InvalidSignatureError:
            continue
    raise Unauthorized("Invalid token signature")
```

**Rotation Process**:
1. Add new secret to Secrets Manager as `jwt_secret_new`
2. Deploy: code reads both, validates with either
3. Wait 15 minutes (access token TTL)
4. Rename: `jwt_secret` → `jwt_secret_previous`, `jwt_secret_new` → `jwt_secret`
5. Wait 7 days (refresh token TTL)
6. Delete `jwt_secret_previous`

### B4: Account Linking (Multiple OAuth Providers)

**Scenario**: User logs in with Google, later wants to add GitHub.

**Current Spec**: Single identity per user (one OAuth provider).

**Resolution**: Out of scope for Phase 1. Document explicitly:
- Single OAuth provider per account
- To switch providers: contact support (manual merge)
- Phase 3+: Account linking API

### B5: Device/Session Management

**Scenario**: User wants to see/revoke sessions on other devices.

**Current Spec (line 2067)**: Listed as out of scope.

**Resolution**: Confirm out of scope. Minimal future API:
```
GET /api/v2/auth/sessions → list active refresh tokens (masked)
DELETE /api/v2/auth/sessions/{hash_prefix} → revoke specific session
```

### B6: Token Size Limits

**Scenario**: User with many roles, JWT exceeds 4KB cookie limit.

**Current Spec**: No size constraints documented.

**Resolution**: Add constraints:
- Maximum 10 roles per user
- Role names max 32 characters
- JWT MUST fit in 4KB (validated at generation)
- If exceeded: log error, use role IDs instead of names

### B7: Clock Skew Between Client/Server

**Scenario**: Client clock wrong by hours, gets 401 immediately after login.

**Current Spec (line 89)**: 60-second leeway for `iat` validation.

**Resolution**:
- `iat` leeway: 60 seconds (already specified)
- `nbf` leeway: 60 seconds (add to spec)
- `exp` leeway: 0 seconds (strict - tokens must not be used after expiry)
- Troubleshooting: If repeated 401s, check client time vs server time

### B8: Safari ITP Compatibility (v2.8 NEW)

**Scenario**: Safari's Intelligent Tracking Prevention (ITP) may delete cookies.

**Problem**: Safari ITP can delete cookies after 7 days if:
- Site is classified as having cross-site tracking capability
- User hasn't interacted with site in 7 days

**Impact on Auth**:
- Refresh token cookie (7-day max-age) may be deleted by ITP
- User returns after 8 days → cookie gone → must re-authenticate
- This is generally acceptable behavior (security feature)

**Why we're compatible**:
1. **First-party context**: Our cookies are same-origin, not third-party
2. **SameSite=Strict**: No cross-site access, reduces ITP triggers
3. **User interaction**: Active users interact regularly, resetting 7-day window
4. **httpOnly**: Not accessible to JavaScript, less "tracking" behavior

**Safari Version Considerations**:
| Safari Version | ITP Behavior | Impact |
|---------------|--------------|--------|
| 12+ | 7-day cap on script-writable storage | N/A (cookies are httpOnly) |
| 13.1+ | Cross-site tracking prevention | N/A (same-origin) |
| 14+ | Full third-party cookie blocking | N/A (first-party) |
| 15.4+ | BroadcastChannel support | ✅ Cross-tab sync works |

**Graceful Degradation**:
```typescript
// frontend/src/hooks/use-session-init.ts

async function initSession() {
  try {
    const response = await authApi.refresh();
    if (response.ok) {
      return response.data;
    }
  } catch (error) {
    // Cookie may have been deleted by ITP
    if (error.status === 401) {
      // Attempt anonymous session
      return await createAnonymousSession();
    }
  }
}
```

**Monitoring**:
- Track "refresh failed → anonymous fallback" rate
- If > 5% on Safari: investigate ITP triggers
- Alert threshold: 10% anonymous fallback rate on Safari

**Testing Safari ITP**:
1. Open Safari → Develop → Enable Intelligent Tracking Prevention Debug Mode
2. Log in, close Safari
3. Wait 8 days (or use fake date in debug mode)
4. Reopen → verify graceful fallback to anonymous

### B9: Mid-Session Tier Upgrade (v2.8 NEW)

**Scenario**: User upgrades from free to paid mid-session.

**Problem**: User's current access token has `tier: "free"`. After Stripe payment:
- Token still says `tier: "free"` for up to 15 minutes
- Premium features should be available immediately
- User expects instant access after payment

**Resolution**: Force token refresh after tier change.

**Backend Flow**:
```python
# Stripe webhook handler
async def handle_subscription_created(event: StripeEvent):
    user_id = event.data.object.metadata.get("user_id")
    tier = map_stripe_plan_to_tier(event.data.object.plan.id)

    # 1. Update user tier in database
    await update_user_tier(user_id, tier)

    # 2. Increment revocation_id to invalidate current tokens
    # This forces all tabs to refresh on next API call
    await increment_revocation_id(user_id)

    # 3. Optional: Send push notification for instant refresh
    await notify_user_tier_changed(user_id, tier)
```

**Frontend Flow**:
```typescript
// frontend/src/lib/stripe/payment-callback.ts

async function handlePaymentSuccess(sessionId: string) {
  // 1. Poll for tier change (webhook may not have fired yet)
  const maxAttempts = 10;
  for (let i = 0; i < maxAttempts; i++) {
    const response = await authApi.refresh();
    if (response.user.tier === 'paid') {
      // 2. Update local state
      useAuthStore.getState().setUser(response.user);

      // 3. Notify other tabs
      crossTabSync.broadcast({
        type: 'LOGIN',  // Triggers refresh in other tabs
        timestamp: Date.now(),
        userId: response.user.id,
      });

      return;
    }
    await sleep(1000);  // Wait 1 second between attempts
  }

  // 4. Fallback: Show success but ask to refresh
  showToast({
    type: 'info',
    message: 'Payment successful! Please refresh the page to access premium features.',
  });
}
```

**Immediate Token Invalidation (Alternative)**:
Instead of polling, backend can immediately invalidate tokens:

```python
async def handle_tier_upgrade(user_id: str, new_tier: str):
    # Update tier
    await update_user_tier(user_id, new_tier)

    # Invalidate ALL current tokens (forces refresh everywhere)
    await increment_revocation_id(user_id)

    # Next API call with old token → 401 → automatic refresh → new tier
```

**Cross-Tab Tier Sync**:
After upgrade, all tabs need new tokens. Two approaches:
1. **Lazy**: Each tab refreshes on next API call (401 triggers refresh)
2. **Eager**: BroadcastChannel triggers immediate refresh in all tabs

**Recommended**: Lazy (simpler, no extra code). 401 interceptor already handles this.

**Edge Cases**:
- **Downgrade**: Same flow - increment revocation_id, force refresh
- **Refund**: Same flow - revert tier, force refresh
- **Failed payment**: Don't change tier until webhook confirms success

---

## Auth Header Transformation (v2.4)

How auth headers flow through each layer:

```
┌─────────────────────────────────────────────────────────────────┐
│ BROWSER                                                         │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Memory: accessToken = "eyJhbGc..."                          │ │
│ │ Cookie: refresh_token=abc123 (httpOnly, not readable by JS) │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                           ↓                                     │
│ Fetch adds:                                                     │
│   Authorization: Bearer eyJhbGc...                              │
│   Cookie: refresh_token=abc123 (automatic)                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ CLOUDFRONT                                                      │
│ Cache Policy:                                                   │
│   - Forward Authorization header (cache key)                    │
│   - Whitelist Cookie: refresh_token                             │
│   - TTL: 0 for /api/v2/auth/* (no caching)                      │
│                                                                 │
│ Response Policy:                                                │
│   - Pass Set-Cookie header unchanged                            │
│   - Add Cache-Control: no-store                                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ API GATEWAY                                                     │
│ CORS Config:                                                    │
│   - Access-Control-Allow-Credentials: true                      │
│   - Access-Control-Allow-Headers: Authorization, Content-Type   │
│                                                                 │
│ Passthrough:                                                    │
│   - Authorization header → Lambda event.headers                 │
│   - Cookie header → Lambda event.headers                        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ LAMBDA                                                          │
│                                                                 │
│ Extract Bearer Token:                                           │
│   auth_header = event["headers"].get("authorization", "")       │
│   if auth_header.startswith("Bearer "):                         │
│       jwt_token = auth_header[7:]                               │
│                                                                 │
│ Extract Refresh Token (for /refresh endpoint only):             │
│   cookie_header = event["headers"].get("cookie", "")            │
│   for cookie in cookie_header.split("; "):                      │
│       if cookie.startswith("refresh_token="):                   │
│           refresh_token = cookie[14:]                           │
│                                                                 │
│ Validate JWT:                                                   │
│   claims = jwt.decode(jwt_token, secret,                        │
│       algorithms=["HS256"],                                     │
│       audience="sentiment-analyzer-api",                        │
│       issuer="sentiment-analyzer",                              │
│       options={"verify_aud": True, "verify_nbf": True}          │
│   )                                                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ DYNAMODB (for refresh token validation)                         │
│                                                                 │
│ Hash token before query:                                        │
│   token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()│
│                                                                 │
│ Query:                                                          │
│   PK = "REFRESH#{token_hash}"                                   │
│                                                                 │
│ Validate:                                                       │
│   - exists? (token valid)                                       │
│   - revoked_at is null? (not revoked)                           │
│   - created_at + 7 days > now? (not expired)                    │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration Requirements

**CloudFront** (`infrastructure/terraform/modules/cloudfront/main.tf`):
```hcl
cache_policy {
  header_behavior = "whitelist"
  headers         = ["Authorization"]
}

origin_request_policy {
  cookie_behavior = "whitelist"
  cookies         = ["refresh_token"]
}
```

**API Gateway** (`infrastructure/terraform/modules/api_gateway/main.tf`):
```hcl
cors_configuration {
  allow_credentials = true
  allow_headers     = ["authorization", "content-type"]
  allow_methods     = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  allow_origins     = [var.frontend_origin]
}
```

---

## Role Future-Proofing (v2.4)

Current implementation supports `anonymous` and `authenticated` roles only. This section documents requirements for future `paid` and `operator` roles.

### Current State

```python
class Role(str, Enum):
    ANONYMOUS = "anonymous"       # Implemented
    AUTHENTICATED = "authenticated" # Implemented
    PAID = "paid"                 # Schema only
    OPERATOR = "operator"         # Schema only
```

### Gaps for Future Roles

| Requirement | Current Status | Gap |
|-------------|---------------|-----|
| Role in JWT claims | ✅ Implemented | - |
| @require_role decorator | ❌ Not implemented | Blocks all role work |
| Role assignment API | ❌ Not specified | Need `POST /users/{id}/roles` |
| Subscription webhook | ❌ Not specified | Need Stripe/billing integration |
| Operator admin UI | ❌ Out of scope | Phase 3+ |

### Schema Additions (Ready for Migration)

```python
# User model additions (nullable, no breaking changes)
class User:
    # Existing fields...

    # Future role fields (nullable defaults)
    subscription_tier: str | None = None  # "free", "pro", "enterprise"
    subscription_active: bool = False
    subscription_expires_at: datetime | None = None
    is_operator: bool = False
    operator_level: int = 0  # 0=none, 1=support, 2=admin, 3=superadmin
    role_assigned_at: datetime | None = None
    role_assigned_by: str | None = None  # user_id or "billing_webhook" or "manual"
```

### Reserved JWT Claims

```python
# Future claims (reserve namespace now)
{
    "sub": "user_id",
    "roles": ["authenticated", "paid"],  # Additive
    "subscription": {                     # Future
        "tier": "pro",
        "active": true,
        "expires_at": 1735689600
    },
    "operator": {                         # Future
        "level": 2,
        "permissions": ["user:read", "user:write"]
    }
}
```

### Implementation Order

1. **Now**: Implement `@require_role` decorator (blocks everything)
2. **Phase 1.5**: Add role fields to User model (migration)
3. **Phase 2**: Add `POST /users/{id}/roles` (operator-only)
4. **Phase 3**: Billing webhook for paid role assignment
5. **Phase 4**: Operator admin UI

---

## Complete DynamoDB Schema Reference (v2.8 NEW)

All auth-related DynamoDB tables and access patterns.

### Table: Users

```
PK: USER#<user_id>
SK: PROFILE

Attributes:
  - user_id: str (UUID)
  - email: str | null
  - email_hash: str (for GSI, privacy)
  - auth_type: "anonymous" | "email" | "google" | "github"
  - tier: str | null ("free", "paid", "operator")
  - revocation_id: int = 0  # v2.8: Increment on password change
  - created_at: ISO8601
  - updated_at: ISO8601
  - subscription_active: bool = false
  - subscription_expires_at: ISO8601 | null

GSI: EmailIndex
  PK: EMAIL#<email_hash>
  SK: USER
```

### Table: Sessions

```
PK: USER#<user_id>
SK: SESSION#<session_id>

Attributes:
  - session_id: str (UUID)
  - user_id: str
  - refresh_token_hash: str (SHA-256)
  - device_info: map {
      user_agent: str,
      ip_address: str,
      geo_location: str | null
    }
  - created_at: ISO8601
  - last_active_at: ISO8601
  - expires_at: ISO8601
  - ttl: int (Unix timestamp for DynamoDB TTL)

GSI: UserSessionsByDate
  PK: USER#<user_id>
  SK: created_at (for oldest-first eviction)
```

### Table: MagicLinkTokens

```
PK: MAGIC#<token_hash>
SK: TOKEN

Attributes:
  - token_hash: str (SHA-256 of token)
  - email: str
  - created_at: ISO8601
  - expires_at: ISO8601
  - consumed_at: ISO8601 | null
  - anonymous_user_id: str | null (for account merge)
  - ttl: int (expires_at + 24h, DynamoDB TTL)
```

### Table: OAuthState (v2.8 NEW)

```
PK: OAUTH#<state>
SK: STATE

Attributes:
  - state: str (32-byte random)
  - provider: "google" | "github"
  - redirect_uri: str
  - ip_address: str
  - user_agent: str
  - created_at: ISO8601
  - expires_at: ISO8601 (5 minutes from creation)
  - ttl: int (expires_at, DynamoDB TTL)
```

### Table: RateLimits (v2.8 NEW)

```
PK: RATE#<key_hash>
SK: COUNT

Attributes:
  - key_hash: str (SHA-256 of rate limit key)
  - count: int
  - window_start: ISO8601
  - ttl: int (window_end, DynamoDB TTL)

Key Patterns:
  - Magic link: "magic_link:{email}"
  - Refresh: "refresh:{user_id}"
  - Login attempts: "login:{ip_address}"
  - Anonymous create: "anon:{ip_address}"
```

### Table: TokenBlocklist (v2.8 - If using blocklist pattern)

```
PK: BLOCK#<token_hash>
SK: REVOKED

Attributes:
  - token_hash: str (SHA-256)
  - user_id: str
  - revoked_at: ISO8601
  - reason: "logout" | "password_change" | "admin_revoke" | "session_limit"
  - ttl: int (original token expiry + 24h buffer)
```

---

## Missing Helper Function Implementations (v2.8 NEW)

These functions were called in specs but not implemented. Complete implementations below.

### G1: store_refresh_token()

```python
# src/lambdas/shared/auth/tokens.py

import hashlib
from datetime import datetime, timedelta, UTC
from boto3.dynamodb.conditions import Key

async def store_refresh_token(
    user_id: str,
    token_hash: str,
    session_id: str,
    device_info: dict,
    expires_at: datetime,
    table,  # DynamoDB Table resource
) -> None:
    """
    Store hashed refresh token in Sessions table.

    NEVER stores plaintext token - only SHA-256 hash.
    """
    now = datetime.now(UTC)
    ttl = int((expires_at + timedelta(hours=24)).timestamp())

    await table.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": f"SESSION#{session_id}",
            "session_id": session_id,
            "user_id": user_id,
            "refresh_token_hash": token_hash,
            "device_info": device_info,
            "created_at": now.isoformat(),
            "last_active_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "ttl": ttl,
        }
    )
```

### G2: get_user_revocation_id()

```python
# src/lambdas/shared/auth/revocation.py

async def get_user_revocation_id(user_id: str, table) -> int:
    """
    Get user's current revocation counter.

    Returns 0 if user not found (new user).
    Increment this on password change to invalidate all tokens.
    """
    response = await table.get_item(
        Key={"PK": f"USER#{user_id}", "SK": "PROFILE"},
        ProjectionExpression="revocation_id",
    )

    if "Item" not in response:
        return 0

    return response["Item"].get("revocation_id", 0)


async def increment_revocation_id(user_id: str, table) -> int:
    """
    Increment revocation counter to invalidate all existing tokens.

    Call this on:
    - Password change
    - Account compromise
    - Admin force-logout
    - Tier upgrade/downgrade (optional)
    """
    response = await table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": "PROFILE"},
        UpdateExpression="SET revocation_id = if_not_exists(revocation_id, :zero) + :one",
        ExpressionAttributeValues={":zero": 0, ":one": 1},
        ReturnValues="UPDATED_NEW",
    )

    return response["Attributes"]["revocation_id"]
```

### G3: session_exists()

```python
# src/lambdas/shared/auth/sessions.py

async def session_exists(user_id: str, session_id: str, table) -> bool:
    """
    Check if session is still active (not revoked or expired).

    Used in JWT validation to ensure session hasn't been evicted.
    """
    if not session_id:
        return False

    response = await table.get_item(
        Key={"PK": f"USER#{user_id}", "SK": f"SESSION#{session_id}"},
        ProjectionExpression="expires_at",
    )

    if "Item" not in response:
        return False

    # Check if expired
    expires_at = datetime.fromisoformat(response["Item"]["expires_at"])
    return datetime.now(UTC) < expires_at


async def revoke_session(
    user_id: str,
    session_id: str,
    reason: str,
    table,
    logger,
) -> bool:
    """
    Revoke a specific session by deleting from Sessions table.

    Returns True if session was deleted, False if not found.
    """
    try:
        await table.delete_item(
            Key={"PK": f"USER#{user_id}", "SK": f"SESSION#{session_id}"},
            ConditionExpression="attribute_exists(PK)",
        )

        logger.info(
            "session_revoked",
            user_id=user_id,
            session_id=session_id,
            reason=reason,
        )
        return True

    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False
```

### G4: create_session_with_limit_enforcement()

```python
# src/lambdas/shared/auth/sessions.py

from boto3.dynamodb.conditions import Key

async def create_session_with_limit_enforcement(
    user_id: str,
    roles: list[str],
    tier: str | None,
    device_info: dict,
    table,
    logger,
) -> str:
    """
    Create session with concurrent session limit enforcement.

    v2.8: Uses role for anonymous, tier for authenticated.

    Returns: session_id
    """
    import uuid

    # Determine limit based on role/tier
    max_sessions = get_session_limit(roles, tier)

    # Get current sessions (oldest first)
    response = await table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}"),
        FilterExpression="begins_with(SK, :prefix)",
        ExpressionAttributeValues={":prefix": "SESSION#"},
        ProjectionExpression="SK, session_id, created_at, device_info",
        ScanIndexForward=True,  # oldest first
    )

    sessions = response.get("Items", [])

    # Evict oldest if at limit
    if len(sessions) >= max_sessions:
        oldest = sessions[0]
        await revoke_session(
            user_id=user_id,
            session_id=oldest["session_id"],
            reason="evicted_by_limit",
            table=table,
            logger=logger,
        )
        logger.info(
            "session_evicted_for_new",
            user_id=user_id,
            evicted_session=oldest["session_id"],
            evicted_device=oldest.get("device_info", {}).get("user_agent", "unknown"),
            current_count=len(sessions),
            max_sessions=max_sessions,
        )

    # Create new session
    session_id = str(uuid.uuid4())

    return session_id
```

### G5: store_oauth_state() / consume_oauth_state()

```python
# src/lambdas/shared/auth/oauth.py

import secrets
from datetime import datetime, timedelta, UTC

async def store_oauth_state(
    provider: str,
    redirect_uri: str,
    ip_address: str,
    user_agent: str,
    table,
) -> str:
    """
    Generate and store OAuth state for CSRF protection.

    Returns: state parameter to include in OAuth URL
    """
    state = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=5)  # Short-lived

    await table.put_item(
        Item={
            "PK": f"OAUTH#{state}",
            "SK": "STATE",
            "state": state,
            "provider": provider,
            "redirect_uri": redirect_uri,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "ttl": int(expires_at.timestamp()),
        }
    )

    return state


async def consume_oauth_state(
    state: str,
    expected_provider: str,
    table,
    logger,
) -> dict | None:
    """
    Validate and consume OAuth state (one-time use).

    Returns state data if valid, None if invalid/expired/already-used.
    Uses conditional delete for atomic consumption.
    """
    try:
        response = await table.delete_item(
            Key={"PK": f"OAUTH#{state}", "SK": "STATE"},
            ConditionExpression="attribute_exists(PK) AND provider = :provider",
            ExpressionAttributeValues={":provider": expected_provider},
            ReturnValues="ALL_OLD",
        )

        item = response.get("Attributes")
        if not item:
            return None

        # Check expiry
        expires_at = datetime.fromisoformat(item["expires_at"])
        if datetime.now(UTC) > expires_at:
            logger.warning("oauth_state_expired", state=state[:8])
            return None

        return item

    except table.meta.client.exceptions.ConditionalCheckFailedException:
        logger.warning("oauth_state_invalid", state=state[:8])
        return None
```

### G6: update_user_tier()

```python
# src/lambdas/shared/auth/users.py

async def update_user_tier(
    user_id: str,
    tier: str,
    table,
    logger,
) -> None:
    """
    Update user's billing tier.

    Called by Stripe webhook on subscription change.
    Should be followed by increment_revocation_id() to force token refresh.
    """
    now = datetime.now(UTC)

    await table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": "PROFILE"},
        UpdateExpression="""
            SET tier = :tier,
                subscription_active = :active,
                updated_at = :now
        """,
        ExpressionAttributeValues={
            ":tier": tier,
            ":active": tier != "free",
            ":now": now.isoformat(),
        },
    )

    logger.info(
        "user_tier_updated",
        user_id=user_id,
        tier=tier,
    )
```

---

## Out of Scope (Future Work)

1. **Paid role assignment** - Requires billing integration (Phase 3+)
2. **Operator role assignment** - Requires admin console (Phase 4+)
3. **Multi-device session management** - Track sessions per device
4. **Token revocation list** - Blacklist compromised tokens (allowlist preferred)
5. ~~**Cross-tab session sync** - BroadcastChannel logout~~ → v2.8: Implemented
6. **Audit logging** - Log all auth events
7. **Account linking** - Multiple OAuth providers per user (see B4)

---

## Testing Requirements

### Unit Tests

1. `@require_role` decorator
   - Returns 401 for missing token
   - Returns 401 for invalid token
   - Returns 403 for missing role
   - Passes for valid token + role
   - Handles `match_all=True` (AND)
   - Handles `match_all=False` (OR)

2. `get_jwt_secret()`
   - Raises if not configured
   - Reads from Secrets Manager (production)
   - Reads from env var (local dev)
   - Validates minimum length (32 chars)
   - NOTE: `get_magic_link_secret()` removed (v2.3: random tokens, no HMAC)

3. JWT generation and validation
   - Round-trips correctly
   - Rejects expired tokens
   - Rejects invalid signature
   - Handles clock skew

### Integration Tests

1. Full auth flow (anonymous → magic link → authenticated)
2. OAuth callback flow
3. Session restore on page load
4. Concurrent refresh deduplication
5. Multi-tab behavior (approximate)

### Integration Tests: Atomic Token Consumption (CRITICAL)

These tests verify the magic link race condition fix (C3).

```python
# tests/integration/test_magic_link_atomic.py
import asyncio
import pytest
from concurrent.futures import ThreadPoolExecutor

class TestAtomicTokenConsumption:
    """
    Verify magic link tokens cannot be consumed twice.

    Race condition scenario:
    1. User clicks magic link
    2. Request 1 starts processing
    3. User clicks link again (impatient)
    4. Request 2 starts processing
    5. Both requests try to consume same token
    6. Only ONE should succeed
    """

    @pytest.mark.integration
    async def test_concurrent_magic_link_consumption_one_succeeds(
        self, test_client, test_email
    ):
        """Two concurrent verify requests - exactly one succeeds."""
        # Create magic link token
        token = await create_magic_link_token(test_email)

        # Simulate concurrent requests
        async def verify():
            return await test_client.get(f"/api/v2/auth/magic-link/verify/{token}")

        results = await asyncio.gather(verify(), verify(), return_exceptions=True)

        # Exactly one should succeed (200), one should fail (410 Gone)
        status_codes = [r.status_code for r in results if hasattr(r, 'status_code')]
        assert status_codes.count(200) == 1, "Exactly one request should succeed"
        assert status_codes.count(410) == 1, "Exactly one request should get 410 Gone"

    @pytest.mark.integration
    async def test_sequential_magic_link_reuse_fails(self, test_client, test_email):
        """Second use of consumed token returns 410 Gone."""
        token = await create_magic_link_token(test_email)

        # First use
        response1 = await test_client.get(f"/api/v2/auth/magic-link/verify/{token}")
        assert response1.status_code == 200

        # Second use
        response2 = await test_client.get(f"/api/v2/auth/magic-link/verify/{token}")
        assert response2.status_code == 410
        assert "already used" in response2.json().get("detail", "").lower()

    @pytest.mark.integration
    async def test_expired_magic_link_returns_410(self, test_client, test_email):
        """Expired token returns 410 Gone, not 401."""
        token = await create_magic_link_token(test_email, expires_in_seconds=-1)

        response = await test_client.get(f"/api/v2/auth/magic-link/verify/{token}")
        assert response.status_code == 410
        assert "expired" in response.json().get("detail", "").lower()

    @pytest.mark.integration
    def test_high_concurrency_stress(self, test_client, test_email):
        """100 concurrent requests - exactly one succeeds."""
        token = create_magic_link_token_sync(test_email)

        def verify():
            return test_client.get(f"/api/v2/auth/magic-link/verify/{token}")

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(verify) for _ in range(100)]
            results = [f.result() for f in futures]

        success_count = sum(1 for r in results if r.status_code == 200)
        gone_count = sum(1 for r in results if r.status_code == 410)

        assert success_count == 1, f"Expected 1 success, got {success_count}"
        assert gone_count == 99, f"Expected 99 gone, got {gone_count}"
```

### Security Tests

1. XSS cannot read tokens (no localStorage, httpOnly cookies)
2. CSRF blocked by SameSite + Bearer auth
3. Hardcoded secrets fail to start
4. Rate limiting on `/refresh`

---

## Concurrent Session Limits (v2.6, updated v2.8)

### Problem

Users can have unlimited active sessions across devices. This creates:
1. Security risk: Compromised devices remain active indefinitely
2. Operational cost: Token storage grows unbounded
3. UX confusion: Which devices are logged in?

### Policy (v2.8 Clarification)

**Session limits use ROLE for anonymous, TIER for authenticated:**

| Lookup Key | Max Sessions | Eviction Policy | Notes |
|------------|--------------|-----------------|-------|
| role=`anonymous` | 1 | Replace existing | v2.8: Use role, not tier (anonymous has tier=null) |
| tier=`free` | 3 | Oldest evicted | Default for authenticated users |
| tier=`paid` | 5 | Oldest evicted | Subscription users |
| tier=`operator` | 10 | Oldest evicted | Internal team |

**A6 FIX**: Anonymous users limited to 1 session to prevent DOS via session exhaustion.
Anonymous sessions are ephemeral and should not persist across devices.

**v2.8 Note**: Anonymous has `tier: null` (no billing relationship). Session limit lookup
uses role membership, not tier field. This is consistent with role vs tier separation.

### Implementation (v2.8 Updated)

```python
# src/lambdas/shared/auth/session_manager.py

# Session limits by tier (for authenticated users)
SESSION_LIMITS_BY_TIER = {
    "free": 3,
    "paid": 5,
    "operator": 10,
}

# Anonymous is special: no tier, use role
ANONYMOUS_SESSION_LIMIT = 1


def get_session_limit(roles: list[str], tier: str | None) -> int:
    """
    Get max concurrent sessions for user.

    v2.8: Anonymous uses role check (has no tier).
    Authenticated users use tier-based limits.
    """
    # Anonymous users: role-based limit (tier is null)
    if "anonymous" in roles:
        return ANONYMOUS_SESSION_LIMIT

    # Authenticated users: tier-based limit
    return SESSION_LIMITS_BY_TIER.get(tier or "free", 3)


async def create_session(
    user_id: str,
    roles: list[str],
    tier: str | None,
    device_info: dict,
) -> str:
    """Create new session, evicting oldest if limit exceeded."""
    max_sessions = get_session_limit(roles, tier)

    # Get current sessions ordered by created_at
    sessions = await get_active_sessions(user_id)

    if len(sessions) >= max_sessions:
        # Evict oldest
        oldest = sessions[0]
        await revoke_session(oldest.session_id, reason="evicted_by_limit")

        # Audit log
        logger.info(
            "session_evicted",
            user_id=user_id,
            evicted_session=oldest.session_id,
            device=oldest.device_info.get("user_agent", "unknown"),
            reason="max_sessions_exceeded",
        )

    # Create new session
    return await create_new_session(user_id, device_info)
```

### DynamoDB Schema

```
Table: Sessions
PK: USER#<user_id>
SK: SESSION#<session_id>
Attributes:
  - created_at (ISO8601)
  - device_info (map: user_agent, ip, geo)
  - last_active_at (ISO8601)
  - refresh_token_hash (string)

GSI: UserSessionsByDate
  PK: USER#<user_id>
  SK: created_at
```

### Session Visibility Endpoint (Future)

```
GET /api/v2/auth/sessions
Response:
{
  "sessions": [
    {
      "session_id": "sess_abc123",
      "device": "Chrome on macOS",
      "location": "San Francisco, CA",
      "last_active": "2026-01-03T12:00:00Z",
      "current": true
    }
  ],
  "max_sessions": 5
}

DELETE /api/v2/auth/sessions/{session_id}
→ 204 No Content (revokes specific session)
```

---

## Password Change Behavior (v2.6)

### Problem

When a user changes their password:
1. Existing tokens remain valid until expiry
2. Attacker with stolen token can access account for up to 7 days
3. No way to "log out everywhere"

### Policy

**Password change MUST invalidate ALL existing refresh tokens.**

### Implementation

```python
# src/lambdas/dashboard/auth.py

async def change_password(user_id: str, old_password: str, new_password: str):
    """Change password and invalidate all sessions."""
    # 1. Verify old password
    if not await verify_password(user_id, old_password):
        raise AuthError("AUTH_007", "Invalid current password")

    # 2. Update password hash
    await update_password_hash(user_id, new_password)

    # 3. Invalidate ALL refresh tokens
    revoked_count = await revoke_all_sessions(
        user_id,
        reason="password_changed",
        exclude_current=False,  # Even current session
    )

    # 4. Audit log
    logger.info(
        "password_changed",
        user_id=user_id,
        sessions_revoked=revoked_count,
    )

    # 5. Force client to re-authenticate
    return {"message": "Password changed. Please log in again."}
```

### DynamoDB Pattern

```python
async def revoke_all_sessions(user_id: str, reason: str, exclude_current: bool = False):
    """Atomic batch revocation of all user sessions."""
    # Query all sessions
    response = await table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}"),
        FilterExpression=Attr("SK").begins_with("SESSION#"),
    )

    # Batch delete with reason logging
    with table.batch_writer() as batch:
        for item in response["Items"]:
            if exclude_current and item["session_id"] == current_session_id:
                continue
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    return len(response["Items"])
```

### Client Behavior

On password change response:
1. Clear memory tokens
2. Clear httpOnly cookie (via Set-Cookie with past expiry)
3. Redirect to login page
4. Show toast: "Password changed. Please log in with your new password."

---

## Error Code Taxonomy (v2.6)

### Problem

Auth errors return inconsistent messages:
- Sometimes HTTP status only
- Sometimes detail in body
- No machine-readable error codes
- Difficult to localize

### Standard Error Response

```json
{
  "error": {
    "code": "AUTH_003",
    "message": "Token has expired",
    "details": {
      "expired_at": "2026-01-03T12:00:00Z",
      "action": "refresh"
    }
  }
}
```

### Error Code Registry

| Code | HTTP | Message | Client Action |
|------|------|---------|---------------|
| `AUTH_001` | 401 | Token signature invalid | Clear tokens, redirect to login |
| `AUTH_002` | 401 | Token malformed | Clear tokens, redirect to login |
| `AUTH_003` | 401 | Token expired | Call `/refresh` |
| `AUTH_004` | 401 | Token not yet valid | Wait and retry (clock skew) |
| `AUTH_005` | 401 | Token audience invalid | Clear tokens, redirect to login |
| `AUTH_006` | 401 | Session revoked | Clear tokens, redirect to login |
| `AUTH_007` | 401 | Invalid credentials | Show error, allow retry |
| `AUTH_008` | 403 | Insufficient permissions | Show access denied page |
| `AUTH_009` | 429 | Rate limit exceeded | Show retry-after, disable button |
| `AUTH_010` | 410 | Magic link invalid | Request new magic link |
| `AUTH_011` | 400 | Token format error | Resend request with correct format |
| `AUTH_012` | 400 | OAuth state invalid | Restart OAuth flow |

**A12 FIX - Error Response Security Guidelines**:

| DO | DON'T |
|----|-------|
| `AUTH_007: "Invalid credentials"` | `AUTH_007: "User not found"` or `"Wrong password"` |
| `AUTH_010: "Magic link invalid"` | `AUTH_010: "Magic link expired"` or `"Magic link already used"` |
| Log user_id hash internally | Include user_id in error response |
| Use consistent response time | Return faster for non-existent users |

**Why**: Distinguishing between "expired" and "used" allows attackers to:
1. Confirm a magic link was valid (it was used, not expired)
2. Infer user activity patterns
3. Enumerate valid email addresses

**Timing Attack Prevention**:
```python
# src/lambdas/dashboard/auth.py

async def verify_magic_link(token: str):
    """
    A12 FIX: Constant-time validation to prevent timing attacks.
    """
    start = time.monotonic()
    MIN_RESPONSE_TIME = 0.1  # 100ms minimum

    try:
        result = await consume_magic_link_token(token)
        return result
    except TokenInvalidError:
        # Same error for expired, used, or never-existed
        raise AuthError("AUTH_010", "Magic link invalid", 410)
    finally:
        # Ensure minimum response time
        elapsed = time.monotonic() - start
        if elapsed < MIN_RESPONSE_TIME:
            await asyncio.sleep(MIN_RESPONSE_TIME - elapsed)
```

### Implementation

```python
# src/lambdas/shared/errors/auth_errors.py
from dataclasses import dataclass
from typing import Any

@dataclass
class AuthError(Exception):
    code: str
    message: str
    http_status: int
    details: dict[str, Any] | None = None

    def to_response(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details or {},
            }
        }

# Registry (A12 FIX: Generic messages to prevent information leakage)
AUTH_ERRORS = {
    "AUTH_001": AuthError("AUTH_001", "Token signature invalid", 401),
    "AUTH_002": AuthError("AUTH_002", "Token malformed", 401),
    "AUTH_003": AuthError("AUTH_003", "Token expired", 401, {"action": "refresh"}),
    "AUTH_004": AuthError("AUTH_004", "Token not yet valid", 401, {"action": "retry"}),
    "AUTH_005": AuthError("AUTH_005", "Token audience invalid", 401),
    "AUTH_006": AuthError("AUTH_006", "Session revoked", 401),
    "AUTH_007": AuthError("AUTH_007", "Invalid credentials", 401),  # A12: NOT "user not found" or "wrong password"
    "AUTH_008": AuthError("AUTH_008", "Insufficient permissions", 403),
    "AUTH_009": AuthError("AUTH_009", "Rate limit exceeded", 429),
    "AUTH_010": AuthError("AUTH_010", "Magic link invalid", 410),  # A12: NOT "expired" or "used"
    "AUTH_011": AuthError("AUTH_011", "Token format error", 400),  # A5: Query param token rejected
    "AUTH_012": AuthError("AUTH_012", "OAuth state invalid", 400),  # A8: CSRF protection
}

def raise_auth_error(code: str, **details):
    error = AUTH_ERRORS[code]
    if details:
        error = AuthError(error.code, error.message, error.http_status, details)
    raise error
```

### Client Error Handling

```typescript
// frontend/src/lib/api/error-handler.ts
const AUTH_ERROR_ACTIONS: Record<string, () => void> = {
  AUTH_001: () => clearTokensAndRedirect(),
  AUTH_002: () => clearTokensAndRedirect(),
  AUTH_003: () => refreshToken(),
  AUTH_004: () => setTimeout(retryRequest, 5000),
  AUTH_005: () => clearTokensAndRedirect(),
  AUTH_006: () => clearTokensAndRedirect(),
  AUTH_007: () => showError("Invalid credentials"),
  AUTH_008: () => showAccessDenied(),
  AUTH_009: (retryAfter) => disableButtonFor(retryAfter),
  AUTH_010: () => showMagicLinkInvalid(),  // A12 FIX: Generic message
  AUTH_011: () => showError("Request format error"),  // A5: Query param rejection
  AUTH_012: () => restartOAuthFlow(),  // A8: CSRF protection
};
```

---

## JWT_SECRET Rotation Runbook (v2.6)

### Problem

No documented procedure for rotating JWT_SECRET in production:
1. How to rotate without logging everyone out?
2. How to handle in-flight requests?
3. How to roll back if something goes wrong?

### Rotation Strategy: Dual-Key Window

Support TWO valid secrets during rotation window:
1. `JWT_SECRET_PRIMARY` - New key (used for signing)
2. `JWT_SECRET_SECONDARY` - Old key (accepted for validation only)

### Rotation Procedure

**Duration**: 15 minutes + token TTL buffer (15 min access + 7 day refresh)

```bash
# Step 1: Generate new secret
NEW_SECRET=$(openssl rand -base64 32)

# Step 2: Update Secrets Manager (add as secondary first)
aws secretsmanager put-secret-value \
  --secret-id sentiment-analyzer/jwt-secrets \
  --secret-string '{
    "primary": "<CURRENT_SECRET>",
    "secondary": "<NEW_SECRET>"
  }'

# Step 3: Deploy Lambda (picks up dual-key validation)
# Wait for all instances to refresh (5-10 minutes)

# Step 4: Swap primary and secondary
aws secretsmanager put-secret-value \
  --secret-id sentiment-analyzer/jwt-secrets \
  --secret-string '{
    "primary": "<NEW_SECRET>",
    "secondary": "<CURRENT_SECRET>"
  }'

# Step 5: Wait for token TTL (7 days for full safety, 15 min for access tokens)

# Step 6: Remove secondary (old) key
aws secretsmanager put-secret-value \
  --secret-id sentiment-analyzer/jwt-secrets \
  --secret-string '{
    "primary": "<NEW_SECRET>",
    "secondary": null
  }'
```

### Implementation

```python
# src/lambdas/shared/config/secrets.py
import json
from functools import lru_cache

@lru_cache(maxsize=1)
def get_jwt_secrets() -> tuple[str, str | None]:
    """Get primary and optional secondary JWT secrets."""
    secret_string = get_secret("sentiment-analyzer/jwt-secrets")
    secrets = json.loads(secret_string)
    return secrets["primary"], secrets.get("secondary")

def validate_jwt_signature(token: str) -> dict:
    """Validate JWT with primary, fallback to secondary."""
    primary, secondary = get_jwt_secrets()

    try:
        return jwt.decode(token, primary, algorithms=["HS256"])
    except jwt.InvalidSignatureError:
        if secondary:
            return jwt.decode(token, secondary, algorithms=["HS256"])
        raise
```

### Rollback Procedure

If rotation causes issues:

```bash
# Immediate rollback: swap primary/secondary back
aws secretsmanager put-secret-value \
  --secret-id sentiment-analyzer/jwt-secrets \
  --secret-string '{
    "primary": "<OLD_SECRET>",
    "secondary": "<NEW_SECRET>"
  }'

# Force Lambda refresh
aws lambda update-function-configuration \
  --function-name sentiment-analyzer-dashboard \
  --environment "Variables={FORCE_REFRESH=$(date +%s)}"
```

### Monitoring

During rotation, monitor:
- `AuthError.AUTH_001` spike (signature invalid)
- `/refresh` 401 rate
- CloudWatch Logs for "secondary key used" events

---

## Logging PII Guidelines (v2.6)

### Problem

Auth flows handle sensitive data. What gets logged?
- Email addresses (PII)
- IP addresses (PII in some jurisdictions)
- User IDs (pseudonymous but linkable)
- Token fragments (security risk)

### Policy

| Data | Log? | Format | Retention |
|------|------|--------|-----------|
| User ID | Yes | Full | 90 days |
| Email | Hash only | SHA256 prefix (8 chars) | 90 days |
| IP Address | Yes | Full (operational need) | 30 days |
| User Agent | Yes | Full | 30 days |
| Access Token | Never | - | - |
| Refresh Token | Never | - | - |
| Token Claims | Subset only | `sub`, `roles`, `exp` | 90 days |
| Passwords | Never | - | - |
| Magic Link Token | Never | - | - |

### Implementation

```python
# src/lambdas/shared/logging/sanitizer.py
import hashlib

def hash_email(email: str) -> str:
    """Hash email for logging (8 char prefix)."""
    return hashlib.sha256(email.encode()).hexdigest()[:8]

def sanitize_claims(claims: dict) -> dict:
    """Extract only safe claims for logging."""
    SAFE_CLAIMS = {"sub", "roles", "exp", "iat", "tier"}
    return {k: v for k, v in claims.items() if k in SAFE_CLAIMS}

def log_auth_event(event_type: str, **kwargs):
    """Log auth event with PII sanitization."""
    sanitized = {}

    for key, value in kwargs.items():
        if key == "email" and value:
            sanitized["email_hash"] = hash_email(value)
        elif key in ("access_token", "refresh_token", "password", "magic_link"):
            continue  # Never log
        elif key == "claims" and isinstance(value, dict):
            sanitized["claims"] = sanitize_claims(value)
        else:
            sanitized[key] = value

    logger.info(event_type, **sanitized)
```

### Audit Events

All auth events MUST be logged with:
- `timestamp` (ISO8601)
- `event_type` (login_success, login_failure, logout, session_revoked, etc.)
- `user_id` (if known)
- `ip_address`
- `user_agent`
- `result` (success/failure)
- `reason` (for failures)

```python
# Example audit log entry
{
    "timestamp": "2026-01-03T12:00:00Z",
    "event_type": "login_success",
    "user_id": "user-123",
    "email_hash": "a1b2c3d4",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "auth_method": "magic_link",
    "session_id": "sess_abc123",
}
```

---

## Cookie Security Hardening (v2.6, updated v2.8)

### Problem

`cookies.ts` uses incorrect settings:
- `SameSite: Lax` (should be `Strict`)
- `Path: /` (should be `/api/v2/auth/refresh` per v2.8)

### Correct Settings (v2.8)

| Attribute | Value | Reason |
|-----------|-------|--------|
| `HttpOnly` | `true` | Prevents XSS token theft |
| `Secure` | `true` | HTTPS only |
| `SameSite` | `Strict` | Prevents CSRF |
| `Path` | `/api/v2/auth/refresh` | v2.8: Minimum exposure (refresh only) |
| `Domain` | (not set) | Current domain only |
| `Max-Age` | `604800` | 7 days (refresh token) |

### Why Strict, Not Lax

`Lax` allows cookies on top-level navigation (clicking links).
`Strict` blocks cookies on ALL cross-site requests.

**Risk with Lax**: Attacker emails link `https://evil.com/redirect?to=https://api.example.com/api/v2/auth/refresh`. User clicks, browser sends cookie, attacker captures new tokens.

**With Strict**: Cross-site navigation does NOT send cookies. User must already be on same-origin.

### Path Restriction (v2.8 Update)

`Path: /` exposes refresh cookie to:
- `/api/v2/metrics` (not needed)
- `/api/v2/admin` (not needed)
- Any future endpoint

~~`Path: /api/v2/auth` limits cookie to:~~
~~- `/api/v2/auth/refresh` (needed)~~
~~- `/api/v2/auth/logout` (needed)~~

**v2.8**: `Path: /api/v2/auth/refresh` limits cookie to:
- `/api/v2/auth/refresh` ONLY

**Why not include `/signout`?** (v2.8)
- Signout uses JWT session_id (`sid` claim) to identify session, not cookie
- Signout endpoint receives `Authorization: Bearer` header, not cookie
- This is MORE secure: anonymous users cannot terminate sessions
- Cookie is cleared via `Set-Cookie` with matching path, doesn't need to be received

### Implementation (Lambda Response) - v2.8 Updated

```python
# src/lambdas/shared/auth/cookies.py

def set_refresh_cookie(response: dict, token: str, max_age: int = 604800) -> dict:
    """Set httpOnly refresh token cookie with security hardening."""
    cookie_parts = [
        f"refresh_token={token}",
        f"Max-Age={max_age}",
        "Path=/api/v2/auth/refresh",  # v2.8: Narrowed to refresh endpoint only
        "HttpOnly",
        "Secure",
        "SameSite=Strict",
    ]

    response.setdefault("multiValueHeaders", {})
    response["multiValueHeaders"]["Set-Cookie"] = ["; ".join(cookie_parts)]
    return response

def clear_refresh_cookie(response: dict) -> dict:
    """Clear refresh token cookie on logout."""
    cookie_parts = [
        "refresh_token=",
        "Max-Age=0",
        "Path=/api/v2/auth/refresh",  # v2.8: Must match set path
        "HttpOnly",
        "Secure",
        "SameSite=Strict",
    ]

    response.setdefault("multiValueHeaders", {})
    response["multiValueHeaders"]["Set-Cookie"] = ["; ".join(cookie_parts)]
    return response
```

### DELETE cookies.ts

The file `frontend/src/lib/cookies.ts` MUST be deleted entirely:
1. It sets cookies from JavaScript (not httpOnly)
2. It uses `SameSite: Lax` (wrong)
3. It uses `Path: /` (wrong)
4. Cookies MUST be set by Lambda response headers only
