# Implementation Plan: OAuth Callback Route Handler

**Branch**: `1192-oauth-callback-route` | **Date**: 2026-01-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1192-oauth-callback-route/spec.md`

## Summary

Create a Next.js route handler at `/auth/callback` to receive OAuth provider redirects and complete the authentication flow. The page extracts authorization code and provider from URL parameters, calls the existing `handleCallback()` function from `useAuth` hook, and displays loading/success/error states following the established pattern from `/auth/verify`.

## Technical Context

**Language/Version**: TypeScript 5.x + Next.js 14.2.21
**Primary Dependencies**: React 18, Zustand (auth-store), framer-motion (animations), lucide-react (icons)
**Storage**: N/A (uses existing auth-store)
**Testing**: Vitest + React Testing Library
**Target Platform**: Web browser (Next.js App Router)
**Project Type**: Web application (frontend-only change)
**Performance Goals**: Page load < 100ms, token exchange < 3s
**Constraints**: Must use existing useAuth hook, follow verify page patterns
**Scale/Scope**: Single route, ~150 LOC

## Constitution Check

_GATE: Must pass before implementation._

- [x] No new external dependencies (uses existing framer-motion, lucide-react)
- [x] No new data models (uses existing auth types)
- [x] No backend changes (frontend-only)
- [x] Follows established patterns (mirrors /auth/verify)
- [x] No security regressions (delegates to existing handleCallback)

## Project Structure

### Documentation (this feature)

```text
specs/1192-oauth-callback-route/
├── spec.md              # Feature specification
├── plan.md              # This file
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Implementation tasks (created by /speckit.tasks)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── app/
│   │   └── auth/
│   │       ├── signin/page.tsx      # Existing - OAuth buttons here
│   │       ├── verify/page.tsx      # Existing - Pattern reference
│   │       └── callback/page.tsx    # NEW - OAuth callback handler
│   ├── hooks/
│   │   └── use-auth.ts              # Existing - handleCallback() function
│   └── stores/
│       └── auth-store.ts            # Existing - handleOAuthCallback()
└── tests/
    └── unit/
        └── app/
            └── auth/
                └── callback.test.tsx  # NEW - Unit tests
```

**Structure Decision**: Frontend-only change following existing auth route patterns. New route at `/auth/callback` mirrors `/auth/verify` structure.

## Implementation Approach

### Dependency Analysis

**Backend API requires**: `{ code, provider, redirect_uri, state }`
**Current frontend API sends**: `{ provider, code }` (missing state, redirect_uri)

**Scope Decision**: Feature 1192 creates the callback route with provider stored in sessionStorage (temporary solution). Feature 1193 will add proper state/CSRF validation by:
1. Updating `signInWithOAuth` to store state before redirect
2. Updating `exchangeOAuthCode` API to send state and redirect_uri
3. Validating state on callback

### Phase 1: Route Handler

Create `/frontend/src/app/auth/callback/page.tsx` following the exact pattern from `/auth/verify/page.tsx`:

1. **URL Parameter Extraction**:
   - Extract `code` from `searchParams.get('code')`
   - Extract `state` from `searchParams.get('state')`
   - Extract `error` from `searchParams.get('error')` (if provider denied)

2. **Provider Detection** (Temporary - Feature 1193 will improve):
   - Store provider in sessionStorage when initiating OAuth (update `signInWithOAuth`)
   - Retrieve provider from sessionStorage on callback
   - Clear sessionStorage after retrieval
   - If no stored provider, display error "Authentication session expired"

3. **Token Exchange**:
   - Call `handleCallback(code, provider)` from useAuth hook
   - handleCallback internally calls handleOAuthCallback which calls authApi.exchangeOAuthCode

4. **State Machine**:
   ```
   loading → success → redirect to /
           ↘ error → show message + retry
   ```

### Phase 2: UI States

Following `/auth/verify` patterns:

1. **Loading State**: Spinner with "Completing sign in..." message
2. **Success State**: Checkmark with "You're signed in!" + auto-redirect
3. **Error State**: X icon with error message + "Try again" button

### Phase 3: Error Handling

Handle all error scenarios:

1. **Provider Denial**: `error` param in URL → "Authentication cancelled"
2. **Missing Code**: No `code` param → "Invalid callback URL"
3. **Invalid State**: State parsing fails → "Invalid authentication request"
4. **Backend Error**: API returns error → Display error.message
5. **Network Error**: Fetch fails → "Connection error. Please try again."
6. **Conflict**: Email already registered → "This email is already registered..."

### Phase 4: Testing

Unit tests covering:
- URL parameter extraction
- Provider detection from state
- Loading/success/error state rendering
- Error message display for each scenario
- Redirect behavior on success

## Dependencies

### Existing Code (no changes needed)

- `useAuth` hook with `handleCallback(code, provider)`
- `auth-store` with `handleOAuthCallback`
- `authApi.exchangeOAuthCode`
- UI components: `Button` from `@/components/ui/button`

### Backend Requirements (already implemented)

- `/api/v2/auth/oauth/urls` returns URLs with state containing provider
- `/api/v2/auth/oauth/callback` accepts code + provider, returns auth response

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| State format mismatch with backend | Medium | High | Check existing getOAuthUrls implementation for state format |
| Race condition on multiple tabs | Low | Low | Each callback is independent, no shared state mutation |
| Browser back button issues | Low | Medium | Auto-redirect prevents re-verification attempts |

## Acceptance Criteria Mapping

| Spec Requirement | Implementation |
|------------------|----------------|
| FR-001: Route at /auth/callback | `app/auth/callback/page.tsx` |
| FR-002: Extract code and state | `searchParams.get('code')`, `searchParams.get('state')` |
| FR-003: Determine provider | Parse state parameter |
| FR-004: Call handleCallback | `const { handleCallback } = useAuth()` |
| FR-005: Loading indicator | `<Loader2>` with "Completing sign in..." |
| FR-006: Redirect on success | `router.push('/')` after 2s delay |
| FR-007: Error with retry | Error state with Button to `/auth/signin` |
| SC-001: < 3s completion | Token exchange is async, page responsive immediately |
| SC-003: < 100ms loading indicator | Immediate render of loading state |
