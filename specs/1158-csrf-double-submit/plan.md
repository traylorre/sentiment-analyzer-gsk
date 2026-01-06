# Implementation Plan: CSRF Double-Submit Cookie Pattern

**Branch**: `1158-csrf-double-submit` | **Date**: 2026-01-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1158-csrf-double-submit/spec.md`

## Summary

Implement CSRF protection using the double-submit cookie pattern. The backend generates a cryptographically random token, sets it in a JavaScript-readable cookie, and validates that incoming state-changing requests include the same token in the `X-CSRF-Token` header. This protects against cross-site request forgery attacks when SameSite is set to `None` for federation support.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, starlette (Response for cookies)
**Storage**: N/A (stateless tokens)
**Testing**: pytest with TestClient
**Target Platform**: AWS Lambda via Mangum
**Project Type**: Web application (backend API + frontend SPA)
**Performance Goals**: <5ms additional latency per request
**Constraints**: Must not break existing authenticated flows
**Scale/Scope**: All state-changing API endpoints (~15 routes)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| No quick fixes (Amendment 1.6) | PASS | Full speckit workflow followed |
| Never destroy workspace files (Amendment 1.9) | N/A | No file deletions |
| Full speckit workflow (Amendment 1.12) | PASS | specify → plan → tasks → implement |
| Use validators (Amendment 1.14) | PASS | Unit tests will validate behavior |

## Project Structure

### Documentation (this feature)

```text
specs/1158-csrf-double-submit/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # CSRF best practices research
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Implementation tasks (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/lambdas/shared/auth/
└── csrf.py                    # NEW: Token generation and validation

src/lambdas/shared/middleware/
└── csrf_middleware.py         # NEW: CSRF validation dependency

src/lambdas/dashboard/
└── router_v2.py               # MODIFY: Add CSRF dependency to protected routes

tests/unit/middleware/
└── test_csrf.py               # NEW: CSRF validation unit tests

frontend/src/lib/api/
└── client.ts                  # MODIFY: Add X-CSRF-Token header to requests
```

**Structure Decision**: Follows existing patterns - auth utilities in `shared/auth/`, middleware in `shared/middleware/`, router modifications in `dashboard/`.

## Implementation Approach

### Phase 1: Backend CSRF Module

Create `src/lambdas/shared/auth/csrf.py`:
- `CSRF_COOKIE_NAME = "csrf_token"`
- `CSRF_HEADER_NAME = "X-CSRF-Token"`
- `generate_csrf_token() -> str` using `secrets.token_urlsafe(32)`
- `validate_csrf_token(cookie: str | None, header: str | None) -> bool` using `hmac.compare_digest`

### Phase 2: CSRF Middleware

Create `src/lambdas/shared/middleware/csrf_middleware.py`:
- FastAPI dependency function `require_csrf(request: Request) -> None`
- Extract cookie via `request.cookies.get(CSRF_COOKIE_NAME)`
- Extract header via `request.headers.get(CSRF_HEADER_NAME)`
- Validate using `validate_csrf_token()`
- Raise `HTTPException(403)` with error code `AUTH_019` on failure
- Skip validation for safe methods (GET, HEAD, OPTIONS)

### Phase 3: Router Integration

Modify `src/lambdas/dashboard/router_v2.py`:
- Add CSRF dependency to `auth_router` for all state-changing endpoints
- Set CSRF cookie in auth success responses (magic link verify, OAuth callback)
- Exempt paths: `/api/v2/auth/refresh`, `/api/v2/auth/oauth/callback`

### Phase 4: Frontend Integration

Modify `frontend/src/lib/api/client.ts`:
- Read `csrf_token` cookie using `document.cookie` parsing
- Include `X-CSRF-Token` header in all POST/PUT/PATCH/DELETE requests
- Handle 403 CSRF errors gracefully

### Phase 5: Testing

Create comprehensive unit tests:
- Token generation produces expected format
- Validation accepts matching tokens
- Validation rejects mismatched tokens
- Validation rejects missing tokens
- Safe methods bypass validation
- Exempt paths bypass validation

## Complexity Tracking

No constitution violations requiring justification.

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing authenticated flows | Phased rollout, comprehensive tests |
| Frontend not sending header | Clear error messages, fallback handling |
| Clock skew with cookie expiry | Cookie max_age matches session lifetime |
| Timing attacks | Use hmac.compare_digest for constant-time comparison |
