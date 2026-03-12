# Research: Security Headers and Auth Error Codes

**Feature**: 1190-security-headers-error-codes
**Date**: 2026-01-10

## Security Headers (A22)

### Decision: Validate Existing Implementation

**Rationale**: Security headers are already implemented in the codebase. No new implementation needed - only validation and potential CSP enhancement.

**Alternatives Considered**:
- Add duplicate headers in another middleware - Rejected: Would cause header duplication
- Move all headers to CloudFront only - Rejected: Lambda-level provides defense-in-depth

### Current Implementation

**File**: `src/lambdas/shared/middleware/security_headers.py`

```python
SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

API_CSP = "default-src 'none'; frame-ancestors 'none'"
```

**CloudFront**: Response headers policy also sets HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy.

### Gap Analysis

| Header | Spec Requirement | Current Status | Action |
|--------|------------------|----------------|--------|
| X-Content-Type-Options | nosniff | Implemented | None |
| X-Frame-Options | DENY | Implemented | None |
| HSTS | max-age 1 year | Implemented (31536000s) | None |
| Referrer-Policy | strict-origin-when-cross-origin | Implemented | None |
| Permissions-Policy | deny sensitive | Implemented | None |
| CSP | allow Cognito | Restrictive (default-src 'none') | Review |

**CSP Consideration**: Current CSP is very restrictive. For OAuth to work, we may need to allow Cognito endpoints. However, the API endpoints don't serve HTML, so restrictive CSP is correct for APIs.

### Conclusion

A22 is **ALREADY IMPLEMENTED**. No code changes needed. Add unit test to verify headers are present.

---

## Auth Error Codes (A23)

### Decision: Add AUTH_XXX Codes as Separate Enum

**Rationale**: Spec-v2.md defines AUTH_013-AUTH_018 with specific numeric codes. Current codebase uses string enums. Hybrid approach maintains backward compatibility while adding spec-compliant codes.

**Alternatives Considered**:
- Replace all string codes with AUTH_XXX - Rejected: Breaking change, affects all error handling
- Ignore AUTH_XXX format - Rejected: Violates spec-v2.md requirements

### Current Error Pattern

**File**: `src/lambdas/shared/errors_module.py`
```python
class ErrorCode(str, Enum):
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    # String-based, no AUTH_XXX format
```

**File**: `src/lambdas/shared/errors/session_errors.py`
```python
class SessionRevokedException(Exception): ...
class SessionExpiredError(Exception): ...
class TokenAlreadyUsedError(Exception): ...
# Exception classes, no numeric codes
```

### Spec-v2.md Requirements

| Code | HTTP | Message | Use Case |
|------|------|---------|----------|
| AUTH_013 | 401 | Credentials have been changed | Password changed, invalidate session |
| AUTH_014 | 401 | Session limit exceeded | User evicted by new login |
| AUTH_015 | 400 | Unknown OAuth provider | Unsupported provider requested |
| AUTH_016 | 400 | OAuth provider mismatch | State/callback provider mismatch |
| AUTH_017 | 400 | Password requirements not met | Weak password submitted |
| AUTH_018 | 401 | Token audience invalid | Wrong environment (dev/preprod/prod) |

### Implementation Approach

Create new enum in `auth_errors.py`:

```python
class AuthErrorCode(str, Enum):
    """Numeric auth error codes per spec-v2.md."""
    AUTH_013 = "AUTH_013"
    AUTH_014 = "AUTH_014"
    AUTH_015 = "AUTH_015"
    AUTH_016 = "AUTH_016"
    AUTH_017 = "AUTH_017"
    AUTH_018 = "AUTH_018"

AUTH_ERROR_MESSAGES = {
    AuthErrorCode.AUTH_013: "Credentials have been changed",
    AuthErrorCode.AUTH_014: "Session limit exceeded",
    AuthErrorCode.AUTH_015: "Unknown OAuth provider",
    AuthErrorCode.AUTH_016: "OAuth provider mismatch",
    AuthErrorCode.AUTH_017: "Password requirements not met",
    AuthErrorCode.AUTH_018: "Token audience invalid",
}

AUTH_ERROR_STATUS = {
    AuthErrorCode.AUTH_013: 401,
    AuthErrorCode.AUTH_014: 401,
    AuthErrorCode.AUTH_015: 400,
    AuthErrorCode.AUTH_016: 400,
    AuthErrorCode.AUTH_017: 400,
    AuthErrorCode.AUTH_018: 401,
}
```

### Frontend Handlers

**File**: `frontend/src/lib/api/errors.ts` (or similar)

```typescript
export const AUTH_ERROR_HANDLERS: Record<string, () => void> = {
  AUTH_013: () => {
    clearTokens();
    showToast("Your password was changed. Please log in again.");
    redirectToLogin();
  },
  AUTH_014: () => {
    clearTokens();
    showToast("You've been signed out because you logged in on another device.");
    redirectToLogin();
  },
  AUTH_015: () => {
    showError("This login provider is not supported.");
  },
  AUTH_016: () => {
    // Silent restart - likely state corruption
    restartOAuthFlow();
  },
  AUTH_017: () => {
    showPasswordRequirements();
  },
  AUTH_018: () => {
    // Environment mismatch - likely dev vs prod confusion
    clearTokens();
    redirectToLogin();
  },
};
```

### Security Considerations

**Role Leakage Prevention**: Error messages MUST NOT reveal:
- Which roles exist in the system
- Which role the user lacks
- Internal error details or stack traces

**Good**: "Session limit exceeded"
**Bad**: "User evicted because max_sessions=3 for free tier"

---

## Summary

| Item | Status | Action Required |
|------|--------|-----------------|
| A22 - Security Headers | Already Implemented | Verified via existing tests |
| A23 - Error Codes | Implemented | AuthErrorCode enum + handlers added |

## Integration Status (auth.py)

| Code | Integrated | Location | Notes |
|------|------------|----------|-------|
| AUTH_013 | Pending | N/A | Requires password change tracking |
| AUTH_014 | Existing | SessionLimitRaceError | Already raised, maps to this code |
| AUTH_015 | Done | auth.py:2036 | Provider validation added |
| AUTH_016 | Pending | validate_oauth_state | State/provider mismatch check |
| AUTH_017 | N/A | N/A | Password auth (Feature 1192) |
| AUTH_018 | Pending | decode_id_token | Audience validation |

**Note**: AUTH_017 will be integrated with Feature 1192 (Password auth endpoint).
AUTH_013, AUTH_016, AUTH_018 require deeper integration and are documented for future work.
