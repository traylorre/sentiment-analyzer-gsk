# Research: CSRF Double-Submit Cookie Pattern

**Feature**: 1158-csrf-double-submit
**Date**: 2026-01-06

## Token Generation

**Decision**: Use `secrets.token_urlsafe(32)` for 256-bit entropy

**Rationale**:
- Standard library function, no external dependencies
- Produces 43 URL-safe characters from 32 bytes of random data
- Cryptographically secure random number generator
- OWASP recommended approach for stateless CSRF tokens

**Alternatives Considered**:
- HMAC-signed tokens (binds to session) - rejected: adds complexity, session binding not required for our use case since we already validate via refresh_token cookie
- UUID4 - rejected: less entropy (122 bits vs 256 bits)
- Custom random generation - rejected: reinventing the wheel, potential for mistakes

## Cookie Attributes

**Decision**: `httpOnly=False, secure=True, samesite=None, path=/api/v2, max_age=86400`

**Rationale**:
- `httpOnly=False`: JavaScript MUST be able to read the cookie to send in header (core requirement of double-submit pattern)
- `secure=True`: Production runs over HTTPS, prevents interception
- `samesite=None`: Required for cross-origin requests with CloudFront CDN
- `path=/api/v2`: Limit cookie scope to API endpoints only
- `max_age=86400`: 24 hours, aligns with session lifetime

**Alternatives Considered**:
- `samesite=Lax/Strict`: Would be more secure but breaks cross-origin federation requirement
- `path=/`: Broader scope than needed, rejected for principle of least privilege

## Validation Implementation

**Decision**: Use `hmac.compare_digest()` for constant-time comparison

**Rationale**:
- Prevents timing attacks that could leak token value
- Standard library function, battle-tested
- OWASP explicitly recommends constant-time comparison

**Implementation Pattern**:
```python
import hmac

def validate_csrf(cookie_value: str | None, header_value: str | None) -> bool:
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)
```

## Exempt Paths

**Decision**: Exempt `/api/v2/auth/refresh` and `/api/v2/auth/oauth/callback/*`

**Rationale**:
- Refresh endpoint: Uses cookie-only authentication, no JavaScript access needed
- OAuth callbacks: OAuth state parameter provides equivalent CSRF protection (nonce in authorization request)
- Safe methods (GET, HEAD, OPTIONS): Never modify state, always exempt per OWASP

## Middleware Integration

**Decision**: Apply as FastAPI dependency on router, not global middleware

**Rationale**:
- More explicit control over which routes are protected
- Easier to exempt specific endpoints
- Follows existing pattern in codebase (see `no_cache_headers` dependency)
- Can be combined with `Depends()` for composable middleware

## Error Response

**Decision**: Return 403 Forbidden with error code `AUTH_019`

**Rationale**:
- 403 is semantically correct (authenticated but forbidden action)
- Consistent with existing auth error patterns in codebase
- Error code enables programmatic handling by frontend

## Sources

- OWASP CSRF Prevention Cheat Sheet (2024)
- spec-v2.md lines 900-1010
- starlette-csrf package patterns
- Existing codebase patterns in `src/lambdas/shared/`
