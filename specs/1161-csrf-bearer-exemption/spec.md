# Feature 1161: CSRF Exemption for Bearer-Authenticated Endpoints

## Problem Statement

E2E tests are failing with HTTP 403 Forbidden on `/api/v2/auth/signout` and `/api/v2/auth/session/refresh` endpoints after Feature 1158 (CSRF Double-Submit) was implemented.

**Root Cause**: These endpoints were not added to CSRF_EXEMPT_PATHS because they were assumed to be browser-only. However, they are called with Bearer tokens (Authorization header), not cookies, making them not vulnerable to CSRF attacks.

## Background

### CSRF Attack Vector
CSRF attacks exploit the fact that browsers automatically attach cookies to cross-origin requests. An attacker can trick a user's browser into making authenticated requests to a target site.

### Why Bearer Tokens Are Immune
- Bearer tokens are stored in JavaScript memory or localStorage
- They are NOT automatically attached to requests
- An attacker's site cannot access tokens due to Same-Origin Policy
- The attacker would need to steal the token via XSS (a different attack class)

### Current State (Feature 1158)
```python
CSRF_EXEMPT_PATHS = frozenset({
    "/api/v2/auth/refresh",     # Cookie-only auth, no JS access needed
    "/api/v2/auth/anonymous",   # Bootstrap endpoint: no session exists
    "/api/v2/auth/magic-link",  # Magic link request (rate-limited)
})
```

## Solution

Add `/api/v2/auth/signout` and `/api/v2/auth/session/refresh` to CSRF_EXEMPT_PATHS with clear documentation explaining why Bearer-authenticated endpoints are exempt.

### Rationale for Each Endpoint

| Endpoint | Auth Method | CSRF Vulnerable? | Exemption Reason |
|----------|-------------|------------------|------------------|
| `/signout` | Bearer token | No | Token not auto-attached |
| `/session/refresh` | Bearer token | No | Token not auto-attached |
| `/refresh` | httpOnly cookie | No | Cookie-only, no JS state to protect |

## Implementation

### File: `src/lambdas/shared/auth/csrf.py`

Update CSRF_EXEMPT_PATHS:
```python
CSRF_EXEMPT_PATHS = frozenset({
    "/api/v2/auth/refresh",         # Cookie-only auth, no JS access needed
    "/api/v2/auth/anonymous",       # Bootstrap endpoint: no session exists
    "/api/v2/auth/magic-link",      # Magic link request (rate-limited)
    "/api/v2/auth/signout",         # Bearer token auth, not CSRF-vulnerable
    "/api/v2/auth/session/refresh", # Bearer token auth, not CSRF-vulnerable
})
```

### Security Analysis

**Threat Model Check**:
1. Can attacker forge `/signout` request? No - requires Bearer token attacker can't obtain
2. Can attacker forge `/session/refresh` request? No - requires Bearer token attacker can't obtain
3. Does this weaken security? No - these endpoints already require valid auth tokens

## Test Plan

1. Existing E2E tests should pass (no longer get 403)
2. Unit test: verify endpoints are in CSRF_EXEMPT_PATHS
3. No new tests needed - exemption is security-neutral for Bearer-authenticated endpoints

## References

- Feature 1158: CSRF Double-Submit Cookie Pattern (introduced CSRF validation)
- OWASP CSRF Prevention Cheat Sheet: Bearer tokens are not CSRF-vulnerable
- RFC 6750: Bearer Token Usage
