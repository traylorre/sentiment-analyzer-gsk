# Implementation Plan: Unify Auth-Store API Client

**Branch**: `1121-unify-auth-store-api` | **Date**: 2026-01-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1121-unify-auth-store-api/spec.md`

## Summary

Replace raw `fetch()` calls in `auth-store.ts` with `authApi` methods to route authentication requests to the Lambda backend instead of the Next.js frontend server. This fixes 404 errors for OAuth, magic link, and other auth operations.

## Technical Context

**Language/Version**: TypeScript 5.x (Next.js 14 frontend)
**Primary Dependencies**: Zustand (state management), authApi (centralized API client)
**Storage**: N/A (uses backend storage via API)
**Testing**: Jest/Vitest for unit tests
**Target Platform**: Web browser (Next.js frontend)
**Project Type**: Web application (frontend-only change)
**Performance Goals**: Auth operations complete within 5 seconds
**Constraints**: Must preserve existing error handling patterns
**Scale/Scope**: Single file modification (`auth-store.ts`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Unit tests required | ✓ Pass | Existing auth-store tests will be updated |
| No pipeline bypass | ✓ Pass | Standard PR workflow |
| GPG-signed commits | ✓ Pass | Standard practice |
| TLS for external calls | ✓ Pass | authApi already uses HTTPS via NEXT_PUBLIC_API_URL |
| Error handling | ✓ Pass | Preserving existing try/catch patterns |

No constitution violations. Proceeding with implementation.

## Project Structure

### Documentation (this feature)

```text
specs/1121-unify-auth-store-api/
├── plan.md              # This file
├── research.md          # Method signature mapping
├── quickstart.md        # Implementation summary
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Task breakdown (created by /speckit.tasks)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── stores/
│   │   └── auth-store.ts    # PRIMARY: Replace fetch() with authApi
│   └── lib/
│       └── api/
│           └── auth.ts      # REFERENCE: authApi methods (no changes)
└── tests/
    └── unit/
        └── stores/
            └── auth-store.test.ts  # UPDATE: Verify authApi usage
```

**Structure Decision**: Frontend-only change. Single file modification with test updates.

## Complexity Tracking

No constitution violations requiring justification.

## Method Mapping

| auth-store.ts Method | Current Implementation | Replace With |
|---------------------|----------------------|--------------|
| `signInWithMagicLink` | `fetch('/api/v2/auth/magic-link')` | `authApi.requestMagicLink(email)` |
| `verifyMagicLink` | `fetch('/api/v2/auth/magic-link/verify')` | `authApi.verifyMagicLink(token, sig)` |
| `signInWithOAuth` | `fetch('/api/v2/auth/oauth/urls')` | `authApi.getOAuthUrls()` |
| `handleOAuthCallback` | `fetch('/api/v2/auth/oauth/callback')` | `authApi.exchangeOAuthCode(provider, code)` |
| `refreshSession` | `fetch('/api/v2/auth/refresh')` | `authApi.refreshToken(refreshToken)` |
| `signOut` | `fetch('/api/v2/auth/signout')` | `authApi.signOut()` |

## Signature Differences

The `authApi` methods have slightly different signatures that require adaptation:

1. **verifyMagicLink**: auth-store passes `{token}`, authApi expects `(token, sig)` - need to extract sig from URL
2. **getOAuthUrls**: Returns `{google: string, github: string}` but backend may return nested `{providers: {...}}`
3. **signOut**: auth-store includes Authorization header manually, authApi handles this internally

## Implementation Approach

1. Import `authApi` at top of auth-store.ts (already imported for signInAnonymous)
2. Replace each raw `fetch()` call with corresponding `authApi` method
3. Adapt response handling where types differ
4. Preserve all error handling (try/catch/setError patterns)
5. Run unit tests to verify no regressions
