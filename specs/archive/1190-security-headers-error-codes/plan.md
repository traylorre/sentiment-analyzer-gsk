# Implementation Plan: Security Headers and Auth Error Codes

**Branch**: `1190-security-headers-error-codes` | **Date**: 2026-01-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1190-security-headers-error-codes/spec.md`

## Summary

Validate and extend existing security headers implementation (A22) and add AUTH_013-AUTH_018 error codes (A23) to the error registry. Security headers are largely implemented; error codes need to align with spec-v2.md numeric format.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript/Next.js (frontend)
**Primary Dependencies**: FastAPI (Response headers), Next.js middleware
**Storage**: N/A (header-only change)
**Testing**: pytest (backend), jest (frontend)
**Target Platform**: AWS Lambda + CloudFront
**Project Type**: web (backend + frontend)
**Performance Goals**: No latency impact (headers added synchronously)
**Constraints**: Must not break existing header handling, backward compatible error responses
**Scale/Scope**: All API endpoints affected

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| No unnecessary complexity | PASS | Extending existing middleware pattern |
| Context efficiency | PASS | Small changes, no large file rewrites |
| Cost sensitivity | N/A | No infrastructure cost impact |
| Testing required | PASS | Unit tests for both headers and error codes |

## Project Structure

### Documentation (this feature)

```text
specs/1190-security-headers-error-codes/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── tasks.md             # Phase 2 output
└── checklists/
    └── requirements.md  # Quality checklist
```

### Source Code (affected files)

```text
# Backend - Security Headers (A22)
src/lambdas/shared/middleware/security_headers.py  # Verify completeness

# Backend - Error Codes (A23)
src/lambdas/shared/errors/auth_errors.py           # Add AUTH_013-AUTH_018
src/lambdas/dashboard/auth.py                      # Use new error codes

# Frontend - Error Handlers (A23)
frontend/src/lib/api/errors.ts                     # Add error code handlers
frontend/src/components/auth/AuthError.tsx         # UI for new errors

# Infrastructure - CloudFront (A22)
infrastructure/terraform/modules/cloudfront/main.tf # Verify HSTS config

# Tests
tests/unit/middleware/test_security_headers.py     # Verify headers
tests/unit/errors/test_auth_error_codes.py         # New error codes
frontend/tests/unit/lib/api/errors.test.ts         # Frontend handlers
```

**Structure Decision**: Web application pattern - changes span backend middleware, error definitions, and frontend error handlers.

## Complexity Tracking

No constitution violations. Extending existing patterns without new abstractions.

## Implementation Phases

### Phase 1: Validate Existing Security Headers (A22)

**Current State (from codebase exploration):**

`security_headers.py` already defines:
```python
SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",  # Deprecated but present
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}
```

CloudFront also has response headers policy with HSTS.

**Gap Analysis:**
- All required headers present in Lambda middleware
- CloudFront HSTS configured
- CSP defined as `API_CSP = "default-src 'none'; frame-ancestors 'none'"`
- **A22 may be COMPLETE** - verify via tests

### Phase 2: Add AUTH_013-AUTH_018 Error Codes (A23)

**Current Error Pattern:**
```python
class ErrorCode(str, Enum):
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    # etc.
```

**Spec-v2.md Pattern:**
```python
AUTH_013: "Credentials have been changed"
AUTH_014: "Session limit exceeded"
AUTH_015: "Unknown OAuth provider"
AUTH_016: "OAuth provider mismatch"
AUTH_017: "Password requirements not met"
AUTH_018: "Token audience invalid"
```

**Decision Required**:
- Option A: Add numeric codes alongside existing string enums (hybrid)
- Option B: Replace string enums with numeric codes (breaking change)
- **Recommended**: Option A - Backward compatible, add `AUTH_XXX` as additional error type

### Phase 3: Frontend Error Handlers

Add handlers in `frontend/src/lib/api/errors.ts`:
```typescript
const AUTH_ERROR_HANDLERS: Record<string, () => void> = {
  AUTH_013: () => clearTokensAndRedirect("Your password was changed"),
  AUTH_014: () => clearTokensAndRedirect("Signed in on another device"),
  AUTH_015: () => showError("Unsupported login provider"),
  AUTH_016: () => restartOAuthFlow(),
  AUTH_017: () => showPasswordRequirements(),
  AUTH_018: () => clearTokensAndRedirect(),
};
```

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Error code format | Hybrid (keep string enums + add AUTH_XXX) | Backward compatible |
| Security headers | Validate existing implementation | Already implemented |
| Frontend handlers | Add to existing error handling | Extend pattern |
| CSP customization | Use spec-v2.md CSP_POLICY | More permissive for OAuth |

## Risks

| Risk | Mitigation |
|------|------------|
| Breaking existing error handling | Hybrid approach, add don't replace |
| CSP blocks OAuth | Allow Cognito endpoints in connect-src |
| Frontend crashes on unknown errors | Generic fallback handler |

## Success Metrics

- [ ] All 5 security headers present on API responses (SC-001)
- [ ] CloudFront HSTS max-age >= 31536000 (SC-003)
- [ ] AUTH_013-AUTH_018 error codes defined (SC-004)
- [ ] No role leakage in error messages (SC-005)
- [ ] Frontend handles all codes without crash (SC-006)
