# Tasks: Auth Retry Backoff

**Feature Branch**: `1336-auth-retry-backoff`
**Created**: 2026-04-05

## Phase 1: Core Retry Logic

### T-001: Add sleep utility to auth-helper.ts
- [ ] Add `sleep(ms: number): Promise<void>` helper function above `createAnonymousSession`
- [ ] Keep it module-private (not exported -- no callers need it)
- File: `frontend/tests/e2e/helpers/auth-helper.ts`
- Acceptance: Pure utility, no behavioral change yet

### T-002: Add retry loop to createAnonymousSession
- [ ] Define constants: `MAX_ATTEMPTS = 3`, `BASE_DELAY_MS = 1000`
- [ ] Wrap existing fetch logic in a for-loop (`attempt = 1..MAX_ATTEMPTS`)
- [ ] On successful response (status 201): return JSON immediately (existing behavior)
- [ ] On HTTP error response (non-201): throw immediately with existing error message (no retry)
- [ ] On TypeError (network failure): if not last attempt, log attempt number and wait `BASE_DELAY_MS * 2^(attempt-1)` ms, then continue loop
- [ ] On TypeError on last attempt: throw new Error with message including attempt count and original error
- [ ] Preserve existing JSDoc comment, update to mention retry behavior
- File: `frontend/tests/e2e/helpers/auth-helper.ts`
- Acceptance: AC-1, AC-2, AC-3, AC-4

## Phase 2: Validation

### T-003: Verify no signature changes
- [ ] Confirm `createAnonymousSession` still accepts `(baseUrl: string)` and returns `Promise<{user_id, auth_type, session_expires_at}>`
- [ ] Confirm `setupAuthSession` still accepts `(context: BrowserContext)` and returns `Promise<void>`
- [ ] Confirm no new exports added
- File: `frontend/tests/e2e/helpers/auth-helper.ts`
- Acceptance: AC-5

### T-004: Verify affected tests still compile
- [ ] Run `npx tsc --noEmit` from frontend directory (or equivalent type check)
- [ ] Confirm alerts-crud.spec.ts, navigation.spec.ts import paths unchanged
- Acceptance: AC-5

### T-005: Verify magic-link and session-lifecycle unchanged
- [ ] Confirm zero changes to `magic-link.spec.ts`
- [ ] Confirm zero changes to `session-lifecycle.spec.ts`
- Acceptance: AC-6
