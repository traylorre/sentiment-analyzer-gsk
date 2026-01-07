# Implementation Plan: Refresh Token Cookie-Only Request

**Branch**: `1168-refresh-cookie-only` | **Date**: 2026-01-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1168-refresh-cookie-only/spec.md`

## Summary

Remove refresh token from frontend request body and rely solely on httpOnly cookie for token refresh. The backend (Feature 1160) already extracts the refresh token from the Cookie header. This change completes the frontend side of the httpOnly migration by ensuring refresh tokens are never exposed to JavaScript.

## Technical Context

**Language/Version**: TypeScript 5.x (Next.js frontend)
**Primary Dependencies**: axios (API client), zustand (state management)
**Storage**: N/A (cookie-based, browser-managed)
**Testing**: vitest (frontend unit tests)
**Target Platform**: Web browser
**Project Type**: Web application (frontend portion)
**Performance Goals**: No performance impact (network payload reduction)
**Constraints**: Must maintain backwards compatibility during migration (backend supports both body and cookie)
**Scale/Scope**: Single API function change with caller updates

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security: TLS in transit | PASS | All API calls use HTTPS |
| Security: Secrets not in source | PASS | Tokens in httpOnly cookie, not JS |
| Security: Authentication required | PASS | Cookie-based auth for refresh endpoint |
| Least privilege | PASS | Frontend only has access to access token, not refresh |

**All gates pass. No violations to justify.**

## Project Structure

### Documentation (this feature)

```text
specs/1168-refresh-cookie-only/
├── plan.md              # This file
├── spec.md              # Feature specification
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Task breakdown (created by /speckit.tasks)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   └── lib/
│       └── api/
│           └── auth.ts      # FR-001, FR-002, FR-006: Remove refreshToken param and body
└── tests/
    └── unit/
        └── lib/
            └── api/
                └── auth.test.ts  # Update tests for new signature
```

**Structure Decision**: This is a frontend-only change. No backend modifications needed (Feature 1160 already complete).

## Complexity Tracking

> No violations requiring justification. This is a minimal change.

## Phase 0: Research

**No research required.** All technical context is known:
- Backend already supports cookie extraction (Feature 1160)
- axios client already configured with `withCredentials: true`
- No architectural decisions needed

**Output**: research.md not needed (skip Phase 0)

## Phase 1: Design

### Data Model Changes

**None.** This change only modifies the API call signature, not data structures.

### API Contract Changes

**Before** (current):
```typescript
POST /api/v2/auth/refresh
Content-Type: application/json
Cookie: refresh_token=<token>

Body: { "refreshToken": "<token>" }
```

**After** (this feature):
```typescript
POST /api/v2/auth/refresh
Content-Type: application/json
Cookie: refresh_token=<token>

Body: (empty or undefined)
```

### Implementation Details

1. **auth.ts changes**:
   - Remove `refreshToken` parameter from function signature
   - Remove request body from POST call
   - Remove `RefreshTokenRequest` interface if unused elsewhere

2. **Caller changes**:
   - Find all callers of `authApi.refreshToken()`
   - Update to call without arguments

3. **Test changes**:
   - Update unit tests to reflect new signature
   - Add test verifying empty body

## Agent Context Update

Technology already in project - no update needed.

## Artifacts Generated

- [x] plan.md (this file)
- [ ] research.md (skipped - no unknowns)
- [ ] data-model.md (skipped - no data changes)
- [ ] contracts/ (skipped - contract unchanged, only body removed)

**Ready for**: `/speckit.tasks`
